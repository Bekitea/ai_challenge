# Образ основного приложения: FastAPI REST API + use cases (Python 3.14).
#
# База намеренно Alpine (musl): вендорное расширение sqlite-vec
# (core/infrastructure/persistence/extensions/sqlite_vec/vec0.so) собрано под musl, на glibc-образе оно
# не загрузится. Зависимости ставим через Poetry (pyproject.toml + poetry.lock)
FROM python:3.14-alpine

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    PYTHONDONTWRITEBYTECODE=1

# build-base/libffi-dev/openssl-dev/musl-dev — запасной путь для сборки колёс,
# которых нет под musllinux; libstdc++ — рантайм для C++ расширений;
# curl — healthcheck; sqlite-vec loadable extension требует поддержки
# load_extension в sqlite3 (есть в образе).
RUN apk add --no-cache \
        build-base \
        libffi-dev \
        openssl-dev \
        musl-dev \
        libstdc++ \
        curl

RUN pip install --no-cache-dir poetry

WORKDIR /app

# Слой зависимостей отдельно, чтобы кешировался между сборками.
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-root --no-ansi

COPY . .

# Быстрая проверка, что расширение sqlite-vec грузится в этом окружении.
RUN python test_vec.py

EXPOSE 8080

CMD ["python", "main_api.py"]
