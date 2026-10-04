"""HTTP-сервис реранкинга на CPU (``BAAI/bge-reranker-v2-m3``).

Запускается отдельным контейнером (см. ``Dockerfile``). Предоставляет
TEI-совместимый эндпоинт ``POST /rerank``, с которым общается
``HttpRerankerProvider`` в основном приложении. Основной код приложения
работает на Python 3.14/Alpine и не тянет torch — вся работа с моделью
изолирована здесь (Python 3.12 в контейнере).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import CrossEncoder

MODEL_ID = os.getenv("RERANKER_MODEL_ID", "BAAI/bge-reranker-v2-m3")
DEVICE = os.getenv("RERANKER_DEVICE", "cpu")
MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "512"))
BATCH_SIZE = int(os.getenv("RERANKER_BATCH_SIZE", "32"))
TORCH_THREADS = int(os.getenv("RERANKER_TORCH_THREADS", "0"))

_state: dict[str, CrossEncoder | None] = {"model": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Загружает модель при старте (скачивается в HF-кэш при первом запуске)."""
    if TORCH_THREADS > 0:
        torch.set_num_threads(TORCH_THREADS)
    _state["model"] = CrossEncoder(MODEL_ID, max_length=MAX_LENGTH, device=DEVICE)
    yield
    _state["model"] = None


app = FastAPI(title="Reranker Service", lifespan=lifespan)


class RerankRequest(BaseModel):
    """Запрос на реранкинг (совместим с TEI ``/rerank``)."""

    query: str
    texts: list[str] = Field(default_factory=list)
    top_n: int | None = None
    raw_scores: bool = False
    return_text: bool = False


class RerankItem(BaseModel):
    """Оценённый документ: индекс в исходном ``texts`` и score."""

    index: int
    score: float
    text: str | None = None


@app.get("/health")
def health() -> dict:
    """Проба готовности сервиса."""
    model = _state["model"]
    return {
        "status": "ok" if model is not None else "loading",
        "model": MODEL_ID,
        "device": DEVICE,
    }


@app.post("/rerank", response_model=list[RerankItem])
def rerank(request: RerankRequest) -> list[RerankItem]:
    """Оценивает релевантность ``texts`` запросу и сортирует по score."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    if not request.texts:
        return []

    model = _state["model"]
    if model is None:
        raise HTTPException(status_code=503, detail="model is not loaded yet")

    pairs = [(request.query, text) for text in request.texts]
    scores = model.predict(pairs, batch_size=BATCH_SIZE)

    items = [
        RerankItem(index=index, score=float(score))
        for index, score in enumerate(scores)
    ]
    items.sort(key=lambda item: item.score, reverse=True)
    if request.top_n is not None:
        items = items[: max(0, request.top_n)]
    if request.return_text:
        for item in items:
            item.text = request.texts[item.index]
    return items


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "18080")),
    )
