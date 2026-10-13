# Образ LLM Gateway (Python 3.14, без torch).
#
# Единственный сервис, который ходит в Ollama напрямую. Сериализует запросы
# через Redis-очередь (durable) и отдаёт наружу Ollama-совместимый API.
#
# Контекст сборки — корень репозитория (см. docker-compose.yml), потому что
# сервис лежит в пакете llm_gateway/.
FROM python:3.14-alpine

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# curl — для healthcheck и отладки.
RUN apk add --no-cache curl

WORKDIR /app

COPY llm_gateway/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY llm_gateway/ ./llm_gateway/

EXPOSE 18081

CMD ["python", "-m", "llm_gateway.main"]
