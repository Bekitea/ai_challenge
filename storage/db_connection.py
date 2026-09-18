from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL


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

        Args:
            metadata: Метаданные SQLAlchemy (Base.metadata).
        """
        metadata.create_all(bind=self._engine)

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
