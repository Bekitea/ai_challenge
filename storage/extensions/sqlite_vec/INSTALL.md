# sqlite-vec: установка и обслуживание

Этот каталог содержит вендорное расширение SQLite [sqlite-vec](https://github.com/asg017/sqlite-vec)
(виртуальные таблицы `vec0` для векторного поиска) и загрузчик к нему.

## Состав каталога

| Файл | Назначение |
| --- | --- |
| `__init__.py` | Загрузчик: выбирает бинарник по платформе и грузит его в соединение SQLite |
| `vec0.so` | Собранное расширение для Linux/musl (x86_64) |
| `vec0.dll` | Готовое расширение для Windows (win_amd64), распаковано из PyPI-колеса |
| `sqlite-vec.c`, `sqlite-vec.h` | Исходники amalgamation-сборки (версия 0.1.9) |
| `build.sh` | Пересборка `vec0.so` под текущую musl-систему |
| `LICENSE-MIT`, `LICENSE-APACHE` | Лицензии sqlite-vec |

Загрузчик используется в `storage/db_connection.py`: на каждое новое соединение
SQLAlchemy вешается событие `connect`, которое вызывает `sqlite_vec.load()`.

## Почему не через pip

Пакет `sqlite-vec` на PyPI публикует колёса только под `manylinux` (glibc),
macOS и Windows (`win_amd64`). Для **musl** (Alpine) нет ни `musllinux`-колеса,
ни sdist, поэтому `pip install sqlite-vec` в нашем контейнере установить нельзя.
Именно поэтому расширение вендорится и грузится вручную.

Готовый `loadable-linux-x86_64` из GitHub Releases собран под **glibc** — под musl
он не загрузится, поэтому `.so` для Alpine собираем сами.

## Пересборка `vec0.so` (Linux/musl)

Нужен компилятор и заголовок `sqlite3ext.h`:

```sh
apk add --no-cache sqlite-dev   # даёт /usr/include/sqlite3ext.h (build-base обычно уже есть)
sh storage/extensions/sqlite_vec/build.sh
```

`build.sh` делает ровно это:

```sh
gcc -O3 -fPIC -shared -include sys/types.h sqlite-vec.c -o vec0.so -lm
```

Про `-include sys/types.h`: на glibc типы `u_int8_t/u_int16_t/u_int64_t` приходят
транзитом через `<stdint.h>`, а на musl — нет. Без этого ключа сборка падает с
`error: unknown type name 'u_int8_t'`.

### Обновление исходников до новой версии

```sh
mkdir -p /tmp/sqlite-vec && cd /tmp/sqlite-vec
wget -O amalgamation.tar.gz \
  https://github.com/asg017/sqlite-vec/releases/download/v0.1.9/sqlite-vec-0.1.9-amalgamation.tar.gz
tar xzf amalgamation.tar.gz
cp sqlite-vec.c sqlite-vec.h /path/to/storage/extensions/sqlite_vec/
```

## Обновление `vec0.dll` (Windows)

```sh
# 1. Скачать колесо (файл под win_amd64)
wget -O sqlite_vec.whl \
  https://files.pythonhosted.org/packages/42/89/81b2907cda14e566b9bf215e2ad82fc9b349edf07d2010756ffdb902f328/sqlite_vec-0.1.9-py3-none-win_amd64.whl
# 2. Распаковать нужный файл
unzip -o sqlite_vec.whl sqlite_vec/vec0.dll -d /tmp/sqlite_vec_win
# 3. Положить рядом с загрузчиком
cp /tmp/sqlite_vec_win/sqlite_vec/vec0.dll storage/extensions/sqlite_vec/
```

Актуальную ссылку на колесо можно получить из JSON PyPI:
`https://pypi.org/pypi/sqlite-vec/0.1.9/json` (поле `urls`).

## Добавление других платформ (опционально)

Загрузчик ищет `vec0.dll` только на Windows, иначе — `vec0.so`. Для macOS
(`vec0.dylib` из `macosx`-колеса) или glibc-Linux (`manylinux`-колесо) нужно
будет расширить функцию `_binary_file()` в `__init__.py` и положить
соответствующий бинарник в этот каталог. Также можно поставить пакет
`sqlite-vec` из PyPI (`pip install sqlite-vec`) и использовать `sqlite_vec.load()`
как альтернативный путь.

## Проверка

Для быстрой проверки в корне проекта лежит скрипт `test_vec.py`: он создаёт
in-memory соединение, грузит расширение через загрузчик и проверяет
`vec_version()`, создание `vec0`-таблицы и векторный поиск.

```sh
poetry run python test_vec.py
```

Ожидаемый вывод: версия `('v0.1.9',)`, `distance = (0.0,)`.

На Windows этот же скрипт проверяет загрузку `vec0.dll`; на Linux/musl — `vec0.so`.
Тот же сценарий вручную:

```sh
poetry run python - <<'PY'
import sqlite3
from storage.extensions import sqlite_vec

conn = sqlite3.connect(":memory:")
sqlite_vec.load(conn)
print(conn.execute("select vec_version()").fetchone())  # ('v0.1.9',)
conn.execute("create virtual table v using vec0(a float[3])")
conn.execute("insert into v(rowid, a) values (1, '[1,2,3]')")
print(conn.execute("select distance from v where a match '[1,2,3]' order by distance limit 1").fetchone())
PY
```

## Ограничения

- Windows ARM64: колеса нет (только `win_amd64`) — нужен x64-Python или своя сборка.
- macOS: системный Python не умеет грузить расширения (`no attribute 'enable_load_extension'`),
  нужен Homebrew-Python либо свой `.dylib`.
- `sqlite-vec` до v1: API может меняться между версиями.
