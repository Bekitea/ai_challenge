import os

from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://ai.api.cloud.yandex.net/v1"
API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
FOLDER_ID = os.getenv("YANDEX_CLOUD_FOLDER")
YANDEX_CLOUD_MODEL = "aliceai-llm-flash/latest"

if not API_KEY or not FOLDER_ID:
    raise ValueError(
        "Не найдены YANDEX_CLOUD_API_KEY или YANDEX_CLOUD_FOLDER в переменных окружения!"
    )
