# Отдельный образ для сервиса реранкинга (CPU, linux/amd64).
#
# Работает и на Windows через Docker Desktop. Внутри намеренно Python 3.12
# (а не 3.14 как в основном приложении): для него есть CPU-колёса torch и
# sentence-transformers.
#
# Модель по умолчанию скачивается при первом старте в кэш /models
# (маунтится volume'ом, см. docker-compose.yml). Чтобы «запечь» модель в
# образ (офлайн), соберите с --build-arg PREFETCH_MODEL=BAAI/bge-reranker-v2-m3.
FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libgomp1 нужен torch для OpenMP на CPU.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# CPU-сборка torch (без CUDA), чтобы образ не раздувался.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY server.py .

ARG PREFETCH_MODEL=""
RUN if [ -n "$PREFETCH_MODEL" ]; then \
        python -c "from sentence_transformers import CrossEncoder; CrossEncoder('$PREFETCH_MODEL')"; \
    fi

EXPOSE 18080

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "18080"]
