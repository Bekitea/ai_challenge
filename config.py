import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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

APPLICATION_MODE = os.getenv("APPLICATION_MODE", "PROD").upper()  # TEST, PROD

if APPLICATION_MODE == "TEST":
    # Тестовый режим: изолированное хранилище
    DATABASE_PATH = "./test-data/agents.db"
    FILE_STORAGE_DIR = "./test-data/file_storage"
else:
    # Продакшен режим: основное хранилище
    DATABASE_PATH = "./data/agents.db"
    FILE_STORAGE_DIR = "./data/file_storage"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(FILE_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
