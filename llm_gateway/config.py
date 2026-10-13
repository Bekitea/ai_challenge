"""Конфигурация сервиса LLM Gateway (читается при импорте, как в config.py)."""

import os

# Адрес реальной Ollama (upstream). Gateway — единственный, кто ходит сюда.
OLLAMA_UPSTREAM_URL = os.getenv(
    "OLLAMA_UPSTREAM_URL", "http://localhost:11434"
).rstrip("/")

# Redis для durable-очереди. Пустая строка => in-process очередь (dev/тесты).
LLM_GATEWAY_REDIS_URL = os.getenv("LLM_GATEWAY_REDIS_URL", "")
LLM_GATEWAY_STREAM = os.getenv("LLM_GATEWAY_STREAM", "llm:jobs")
LLM_GATEWAY_GROUP = os.getenv("LLM_GATEWAY_GROUP", "gateway")
LLM_GATEWAY_CONSUMER = os.getenv("LLM_GATEWAY_CONSUMER", "worker-1")

# Сколько ждать ответа на запрос в HTTP-слое gateway (секунды).
QUEUE_WAIT_TIMEOUT = int(os.getenv("QUEUE_WAIT_TIMEOUT", "600"))
# Таймаут одного запроса к Ollama (секунды).
LLM_UPSTREAM_TIMEOUT = int(os.getenv("LLM_UPSTREAM_TIMEOUT", "300"))
# Максимальная длина очереди; при переполнении отдаём 503 (fail fast).
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", "200"))

# TTL ключей ответов/отмены в Redis (секунды).
REPLY_TTL = int(os.getenv("LLM_GATEWAY_REPLY_TTL", "3600"))
# Блокирующее ожидание новых задач потребителем (миллисекунды).
DEQUEUE_BLOCK_MS = int(os.getenv("LLM_GATEWAY_DEQUEUE_BLOCK_MS", "500"))

PORT = int(os.getenv("LLM_GATEWAY_PORT", "18081"))
HOST = os.getenv("LLM_GATEWAY_HOST", "0.0.0.0")
