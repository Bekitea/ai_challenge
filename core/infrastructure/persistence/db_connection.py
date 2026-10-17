from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL
from core.infrastructure.persistence.extensions import sqlite_vec


class DatabaseConnection:
    """
    Технический класс для управления подключениями к базе данных.

    Инкапсулирует создание engine и фабрики сессий, предоставляя
    методы для получения сессий и управления пулом соединений.

    Пример использования:
        db = DatabaseConnection()
        with db.get_session() as session:
            # работа с сессией
        db.close()
    """

    def __init__(
        self,
        database_url: str | None = None,
        echo: bool = False,
        connect_args: dict | None = None,
    ):
        """
        Инициализирует подключение к базе данных.

        Args:
            database_url: URL базы данных. По умолчанию используется DATABASE_URL из config.
            echo: Логгировать ли SQL запросы.
            connect_args: Дополнительные аргументы для подключения.
        """
        self._database_url = database_url or DATABASE_URL
        self._echo = echo
        self._connect_args = connect_args or {}

        self._engine = create_engine(
            self._database_url,
            echo=self._echo,
            connect_args=self._connect_args,
        )

        # Расширение sqlite-vec загружается на каждом новом соединении, если
        # для текущей платформы есть вендорный бинарник (иначе молча пропускаем).
        # Там же включаются PRAGMA, критичные для каскадных удалений и RAG.
        @event.listens_for(self._engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record):
            if not self._database_url.startswith("sqlite"):
                return

            if sqlite_vec.is_available():
                sqlite_vec.load(dbapi_connection)

            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
                if ":memory:" not in self._database_url:
                    cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
            finally:
                cursor.close()

        self._session_factory = sessionmaker(
            bind=self._engine, autoflush=False, expire_on_commit=False
        )

    def get_session(self) -> Session:
        """
        Возвращает новую сессию базы данных.

        Returns:
            Session: Новая сессия SQLAlchemy.
        """
        return self._session_factory()

    def init_tables(self, metadata) -> None:
        """
        Создаёт таблицы в базе данных, если они не существуют.

        Дополнительно для SQLite добавляет недостающие колонки в уже
        существующие таблицы: приложение создаёт схему через ``create_all``
        (а не через alembic), поэтому при добавлении новых полей старая БД
        иначе ломалась бы (`no such column`). Синхронизация только additive —
        колонки добавляются, но ничего не удаляется и не меняется.

        Args:
            metadata: Метаданные SQLAlchemy (Base.metadata).
        """
        metadata.create_all(bind=self._engine)
        self._sync_missing_columns(metadata)

    def _sync_missing_columns(self, metadata) -> None:
        """Добавляет в существующие таблицы колонки, которых нет в БД (SQLite)."""
        if not self._database_url.startswith("sqlite"):
            return

        from sqlalchemy import inspect

        inspector = inspect(self._engine)
        existing_tables = set(inspector.get_table_names())

        with self._engine.begin() as connection:
            for table in metadata.sorted_tables:
                if table.name not in existing_tables:
                    continue
                existing_columns = {
                    column["name"] for column in inspector.get_columns(table.name)
                }
                for column in table.columns:
                    if column.name in existing_columns:
                        continue
                    ddl = self._add_column_ddl(table.name, column)
                    connection.exec_driver_sql(ddl)

    def _add_column_ddl(self, table_name: str, column) -> str:
        """Строит ``ALTER TABLE ... ADD COLUMN ...`` для одной колонки."""
        type_sql = column.type.compile(dialect=self._engine.dialect)
        ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {type_sql}'
        if not column.nullable:
            ddl += f" NOT NULL DEFAULT {self._column_literal_default(column)}"
        return ddl

    @staticmethod
    def _column_literal_default(column) -> str:
        """Подбирает литеральное значение по умолчанию для NOT NULL колонки."""
        server_default = getattr(column, "server_default", None)
        if server_default is not None and getattr(server_default, "arg", None) is not None:
            return str(server_default.arg)

        from sqlalchemy import Boolean, DateTime, Integer, Numeric

        column_type = column.type
        if isinstance(column_type, (Integer, Boolean, Numeric)):
            return "0"
        if isinstance(column_type, DateTime):
            return "CURRENT_TIMESTAMP"
        return "''"

    def close(self) -> None:
        """
        Закрывает все соединения в пуле.

        Вызывается для явного освобождения ресурсов.
        """
        self._engine.dispose()

    @property
    def engine(self):
        """Возвращает объект engine для прямого доступа (если необходимо)."""
        return self._engine
