from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from config import API_KEY, BASE_URL, FOLDER_ID, YANDEX_CLOUD_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, project=FOLDER_ID)


class ModelInfo(BaseModel):
    name: str
    developer: str
    capabilities: list[str]
    is_yandex: bool


def check_model():
    try:
        schema_dict: Any = {
            "type": "json_schema",
            "json_schema": {
                "name": "model_info_schema",
                "strict": True,
                "schema": ModelInfo.model_json_schema(),
            },
        }

        response = client.chat.completions.create(
            model=f"gpt://{FOLDER_ID}/{YANDEX_CLOUD_MODEL}",
            messages=[
                {
                    "role": "system",
                    "content": "Ответь строго в формате JSON по заданной схеме.",
                },
                {"role": "user", "content": "Расскажи о себе."},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format=schema_dict,
        )

        raw_content = response.choices[0].message.content

        validated_data = ModelInfo.model_validate_json(
            raw_content if raw_content else ""
        )

        print("✅ Данные успешно распарсены и валидированы!")
        print(f"Модель: {validated_data.name}")
        print(f"Разработчик: {validated_data.developer}")
        print(f"Возможности: {', '.join(validated_data.capabilities)}")

    except ValidationError as e:
        print(f"❌ Модель вернула JSON, но он не соответствует схеме:\n{e}")
    except Exception as e:
        print(f"❌ Ошибка API: {e}")


if __name__ == "__main__":
    check_model()
