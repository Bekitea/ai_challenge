import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

YANDEX_BASE_URL = "https://ai.api.cloud.yandex.net/v1"
YANDEX_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_CLOUD_FOLDER")
YANDEX_DEFAULT_MODEL = "aliceai-llm-flash/latest"

if not YANDEX_API_KEY or not YANDEX_FOLDER_ID:
    raise ValueError(
        "Не найдены YANDEX_CLOUD_API_KEY или YANDEX_CLOUD_FOLDER в переменных окружения!"
    )

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/agents.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
CHAT_HISTORY_DIR = os.getenv("CHAT_HISTORY_DIR", "./data/chat_history")

Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(CHAT_HISTORY_DIR).mkdir(parents=True, exist_ok=True)
