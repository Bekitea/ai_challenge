import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Настройки Yandex Cloud ---
YANDEX_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
YANDEX_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_CLOUD_FOLDER")

REASONING_EFFORTS = ["none", "low", "medium", "high"]

# --- Провайдеры LLM ---
# Имена провайдеров, которые хранятся в AgentSettings.provider.
LLM_PROVIDER_YANDEX = "yandex"
LLM_PROVIDER_OLLAMA = "ollama"
# Провайдер для чатов, созданных до появления выбора (provider=None).
DEFAULT_PROVIDER = LLM_PROVIDER_YANDEX

# Периодические отчёты Celery неинтерактивны, поэтому для них нужен явный
# провайдер и модель по умолчанию (в обычных чатах дефолтной модели нет —
# пользователь всегда выбирает сам).
DEFAULT_REPORT_PROVIDER = os.getenv("DEFAULT_REPORT_PROVIDER", LLM_PROVIDER_YANDEX)
DEFAULT_REPORT_MODEL = os.getenv("DEFAULT_REPORT_MODEL", "aliceai-llm-flash/latest")

# Таймаут опроса списка моделей у провайдеров. При активном LLM Gateway
# запрос списка моделей тоже проходит очередь и может подождать, пока Ollama
# занята генерацией, поэтому таймаут увеличен.
MODEL_LIST_TIMEOUT = int(os.getenv("MODEL_LIST_TIMEOUT", "60"))

# Таймаут одного чат-запроса к LLM. С включённым LLM Gateway запрос может
# подождать в очереди (пока Ollama занята другим запросом), поэтому таймаут
# заметно больше времени генерации. Должен превышать gateway QUEUE_WAIT_TIMEOUT
# (по умолчанию 600s), чтобы клиент получал осмысленную ошибку самого gateway,
# а не гонку таймаутов.
LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "900"))

# Таймаут LLM-вызовов извлечения памяти (глобальной, профиля задачи и памяти
# задачи диалога). Память — best-effort (сбой не прерывает диалог), но при
# активном gateway вызов тоже проходит очередь, поэтому таймаут увеличен.
MEMORY_LLM_TIMEOUT = int(os.getenv("MEMORY_LLM_TIMEOUT", "120"))
# Число повторов SDK для вызовов памяти. 0 — без повторов, чтобы таймаут
# MEMORY_LLM_TIMEOUT не умножался на количество попыток.
MEMORY_LLM_MAX_RETRIES = int(os.getenv("MEMORY_LLM_MAX_RETRIES", "0"))

# --- Настройки Ollama (Локальные модели и Эмбеддинги) ---
# Автоматически определяем, запущен ли код внутри Docker-контейнера.
# На хосте Ollama доступна как localhost, из контейнера — через
# host.docker.internal (docker.internal не резолвится).
IS_INSIDE_DOCKER = Path("/.dockerenv").exists()
DEFAULT_OLLAMA_URL = (
    "http://host.docker.internal:11434"
    if IS_INSIDE_DOCKER
    else "http://localhost:11434"
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)

# --- LLM Gateway (единый поток запросов к Ollama) ---
# Отдельный прокси-сервис (llm_gateway/), который гарантирует, что в Ollama
# одновременно уходит ровно один запрос, а остальные ждут в очереди (Redis).
# При включении основной бэкенд ходит в Ollama не напрямую, а через gateway —
# это касается чата, эмбеддингов RAG и списка моделей. В TEST режиме выключен
# (там MockLlmProvider), в PROD/LOCAL включается переменной окружения.
LLM_GATEWAY_ENABLED = os.getenv("LLM_GATEWAY_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)
LLM_GATEWAY_URL = os.getenv(
    "LLM_GATEWAY_URL", "http://127.0.0.1:18081"
).rstrip("/")

# Нативный базовый URL Ollama (без ``/v1``) для списка моделей. При активном
# gateway указывает на gateway, иначе — напрямую на Ollama.
OLLAMA_NATIVE_BASE_URL = (
    LLM_GATEWAY_URL if LLM_GATEWAY_ENABLED else OLLAMA_BASE_URL
)

# OpenAI-совместимый эндпоинт Ollama для чата (tool calling, usage-токены).
OLLAMA_OPENAI_BASE_URL = os.getenv(
    "OLLAMA_OPENAI_BASE_URL", f"{OLLAMA_NATIVE_BASE_URL.rstrip('/')}/v1"
)
OLLAMA_DEFAULT_EMBEDDING_MODEL = os.getenv("OLLAMA_DEFAULT_EMBEDDING_MODEL", "bge-m3")

AVAILABLE_EMBEDDING_MODELS = {
    "bge-m3": "BGE-M3 Multilingual Embedding (Local)",
}

# --- Настройки RAG (эмбеддинг, реранкер, чанкинг, поиск) ---
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", OLLAMA_NATIVE_BASE_URL)
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "bge-m3")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
# При активном gateway эмбеддинги ждут очередь так же, как чат, поэтому
# таймаут должен перекрывать QUEUE_WAIT_TIMEOUT gateway.
EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "300"))

# Реранкер по умолчанию включён (per-chat флаг в AgentSettings тоже по
# умолчанию True). Сервис реранкинга — отдельный HTTP-контейнер
# (см. reranker_service/). Адрес — 127.0.0.1, а не localhost: на Windows
# localhost резолвится в ::1 и может попасть в чужой процесс на этом порту.
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() in ("1", "true", "yes")
RERANKER_BASE_URL = os.getenv("RERANKER_BASE_URL", "http://127.0.0.1:18080")
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "bge-reranker-v2-m3")
RERANKER_BATCH_SIZE = int(os.getenv("RERANKER_BATCH_SIZE", "32"))
RERANKER_TIMEOUT = int(os.getenv("RERANKER_TIMEOUT", "60"))
RERANKER_RETRY_COUNT = int(os.getenv("RERANKER_RETRY_COUNT", "1"))

RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "120"))
RAG_VECTOR_TOP_K_PER_KB = int(os.getenv("RAG_VECTOR_TOP_K_PER_KB", "20"))
RAG_CANDIDATE_LIMIT_TOTAL = int(os.getenv("RAG_CANDIDATE_LIMIT_TOTAL", "60"))
RAG_FINAL_TOP_K = int(os.getenv("RAG_FINAL_TOP_K", "5"))

# Порог релевантности RAG в единой шкале [0..1]: при реранкинге это score
# кросс-энкодера, при векторном поиске — 1 - distance/2. Чанки ниже порога
# отбрасываются, и ассистент обязан ответить «Не знаю» и попросить уточнений.
RAG_RELEVANCE_THRESHOLD = float(os.getenv("RAG_RELEVANCE_THRESHOLD", "0.3"))

# --- Память задачи диалога (per-chat) ---
# Память хранит цель диалога, зафиксированные ограничения/термины и уже
# внесённые уточнения. Обновляется через LLM каждые N пользовательских ходов
# и при сжатии контекста, чтобы цель не терялась в длинном диалоге.
TASK_MEMORY_ENABLED = os.getenv("TASK_MEMORY_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
TASK_MEMORY_UPDATE_EVERY_N_MESSAGES = int(
    os.getenv("TASK_MEMORY_UPDATE_EVERY_N_MESSAGES", "3")
)
TASK_MEMORY_WINDOW_MESSAGES = int(os.getenv("TASK_MEMORY_WINDOW_MESSAGES", "12"))

# Загрузка документов из файлов (.txt/.md/.py)
RAG_FILE_EXTENSIONS = {".txt", ".md", ".py"}
RAG_FILE_MAX_BYTES = int(os.getenv("RAG_FILE_MAX_BYTES", str(1024 * 1024)))
RAG_FOLDER_MAX_FILES = int(os.getenv("RAG_FOLDER_MAX_FILES", "100"))

# --- Режим работы приложения ---
# PROD — продакшен (обязательны ключи Yandex Cloud), TEST — моки,
# LOCAL — локальный запуск (например, только Ollama), без обязательных
# ключей Yandex и с изолированным хранилищем ./local-data/.
APPLICATION_MODE = os.getenv("APPLICATION_MODE", "PROD").upper()  # TEST, LOCAL, PROD

if APPLICATION_MODE == "TEST":
    # Тестовый режим: изолированное хранилище для e2e-тестов
    _STORAGE_BASE = "./test-data"
elif APPLICATION_MODE == "LOCAL":
    # Локальный запуск: отдельное хранилище, чтобы не смешивать с продом
    _STORAGE_BASE = "./local-data"
else:
    # Продакшен режим: основное хранилище
    _STORAGE_BASE = "./data"

DATABASE_PATH = f"{_STORAGE_BASE}/agents.db"
FILE_STORAGE_DIR = f"{_STORAGE_BASE}/file_storage"
GLOBAL_MEMORY_PATH = f"{_STORAGE_BASE}/global_memory.pkl"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Создание необходимых директорий
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(FILE_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
Path(GLOBAL_MEMORY_PATH).parent.mkdir(parents=True, exist_ok=True)
