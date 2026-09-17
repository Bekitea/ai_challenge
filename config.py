import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

YANDEX_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
YANDEX_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_CLOUD_FOLDER")
YANDEX_DEFAULT_MODEL = "aliceai-llm-flash/latest"

# Определение режима работы приложения
APPLICATION_MODE = os.getenv("APPLICATION_MODE", "PROD").upper()

if APPLICATION_MODE == "TEST":
    # Тестовый режим: изолированное хранилище
    DATABASE_PATH = "./test-data/agents.db"
    CHAT_HISTORY_DIR = "./test-data/chat_history"
else:
    # Продакшен режим: основное хранилище
    DATABASE_PATH = "./data/agents.db"
    CHAT_HISTORY_DIR = "./data/chat_history"

DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(CHAT_HISTORY_DIR).mkdir(parents=True, exist_ok=True)
