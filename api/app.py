"""Сборка FastAPI-приложения REST API (слой представления).

``build_app`` получает уже готовый ``UseCasesBundle`` (создаётся фабрикой
приложения в ``main_api.py``) и не знает ничего о репозиториях, провайдерах
или бизнес-объекте ``Agent``.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.errors import register_exception_handlers
from api.routers import (
    chats,
    knowledge_bases,
    mcp,
    memory,
    models,
    task_profiles,
)
from use_cases import UseCasesBundle

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def build_app(use_cases: UseCasesBundle) -> FastAPI:
    """Создаёт и настраивает FastAPI-приложение."""
    app = FastAPI(title="AI Chat API", version="0.1.0")
    app.state.use_cases = use_cases

    # CORS нужен только для Vite dev-сервера; в проде фронт раздаётся тем же
    # origin, поэтому политика максимально простая (без аутентификации).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        """Проба готовности сервиса."""
        return {"status": "ok"}

    api = APIRouter()
    api.include_router(models.router)
    api.include_router(chats.router)
    api.include_router(mcp.router)
    api.include_router(knowledge_bases.router)
    api.include_router(task_profiles.router)
    api.include_router(memory.router)
    app.include_router(api, prefix="/api")

    # Раздача собранного React-фронта с того же порта (single origin).
    if FRONTEND_DIST.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(FRONTEND_DIST), html=True),
            name="frontend",
        )
    else:

        @app.get("/")
        def frontend_missing() -> dict:
            return {
                "detail": (
                    "Фронтенд не собран. Выполните "
                    "`cd frontend && npm install && npm run build`."
                )
            }

    return app
