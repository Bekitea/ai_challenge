"""Точка входа LLM Gateway: запускает HTTP-сервер и потребителя очереди."""

from __future__ import annotations

import logging

import uvicorn

from llm_gateway import config
from llm_gateway.server import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = create_app()


def main() -> None:
    """Запускает uvicorn с настройками gateway."""
    uvicorn.run(app, host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
