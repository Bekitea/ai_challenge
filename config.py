import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Настройки Yandex Cloud ---
YANDEX_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
YANDEX_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_CLOUD_FOLDER")
YANDEX_DEFAULT_MODEL = "aliceai-llm-flash/latest"

AVAILABLE_MODELS = {
    "1": ("gpt-oss-120b/latest", "GPT OSS 120B"),
    "2": ("qwen3.6-35b-a3b/latest", "Qwen3.6-35B"),
    "3": ("aliceai-llm-flash/latest", "Alice AI LLM Flash"),
}

REASONING_EFFORTS = ["none", "low", "medium", "high"]

# --- Настройки Ollama (Локальные модели и Эмбеддинги) ---
# Автоматически определяем, запущен ли код внутри Docker-контейнера
IS_INSIDE_DOCKER = Path("/.dockerenv").exists()
DEFAULT_OLLAMA_URL = (
    "http://docker.internal" if IS_INSIDE_DOCKER else "http://localhost:11434"
)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
OLLAMA_DEFAULT_EMBEDDING_MODEL = os.getenv("OLLAMA_DEFAULT_EMBEDDING_MODEL", "bge-m3")

AVAILABLE_EMBEDDING_MODELS = {
    "bge-m3": "BGE-M3 Multilingual Embedding (Local)",
}

# --- Режим работы приложения ---
APPLICATION_MODE = os.getenv("APPLICATION_MODE", "PROD").upper()  # TEST, PROD

if APPLICATION_MODE == "TEST":
    # Тестовый режим: изолированное хранилище
    DATABASE_PATH = "./test-data/agents.db"
    FILE_STORAGE_DIR = "./test-data/file_storage"
    GLOBAL_MEMORY_PATH = "./test-data/global_memory.pkl"
else:
    # Продакшен режим: основное хранилище
    DATABASE_PATH = "./data/agents.db"
    FILE_STORAGE_DIR = "./data/file_storage"
    GLOBAL_MEMORY_PATH = "./data/global_memory.pkl"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Создание необходимых директорий
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(FILE_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
Path(GLOBAL_MEMORY_PATH).parent.mkdir(parents=True, exist_ok=True)
