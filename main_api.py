"""Точка входа REST API + Web UI.

Запуск одной короткой командой:

    python main_api.py

По умолчанию поднимается в режиме ``APPLICATION_MODE=LOCAL`` (реальные
провайдеры вроде Ollama, без обязательных ключей Yandex, хранилище в
``./local-data/``) и раздаёт собранный React-фронт вместе с API на одном
порту ``http://127.0.0.1:8080``.

Переопределяется переменными окружения ``APPLICATION_MODE``, ``API_HOST``,
``API_PORT``. Модуль отвечает только за бутстрап: создаёт use cases через
фабрику и передаёт их слою представления (``core.presentation.api.app``).
"""

from __future__ import annotations

import os

# Режим по умолчанию для веб-демо. Устанавливается ДО импорта модулей проекта,
# потому что config.py читает APPLICATION_MODE при загрузке.
os.environ.setdefault("APPLICATION_MODE", "LOCAL")

from fastapi import FastAPI

from core.di.app_factory import initialize_application
from core.presentation.api.app import FRONTEND_DIST, build_app


def create_app() -> FastAPI:
    """Создаёт FastAPI-приложение с инициализированным набором use cases.

    Один процесс, один набор use cases: MCP-подключения хранятся в памяти
    процесса, поэтому воркер должен быть ровно один.
    """
    use_cases = initialize_application()
    return build_app(use_cases)


def main() -> None:
    """Запускает веб-сервер с настройками по умолчанию для локального демо."""
    import uvicorn

    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8080"))

    if not FRONTEND_DIST.is_dir():
        print(
            "Фронтенд не собран. Выполните:\n"
            "    cd frontend && npm install && npm run build\n"
            "(API всё равно будет доступен под /api)."
        )
    print(f"Веб-интерфейс: http://{host}:{port}")

    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
