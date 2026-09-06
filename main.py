from openai import OpenAI

from config import API_KEY, BASE_URL, FOLDER_ID, YANDEX_CLOUD_MODEL

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, project=FOLDER_ID)


def check_model():
    try:
        response = client.chat.completions.create(
            model=f"gpt://{FOLDER_ID}/{YANDEX_CLOUD_MODEL}",
            messages=[{"role": "user", "content": "Что ты за модель? "}],
            temperature=0.3,
            max_tokens=1500,
        )

        print("Ответ модели:")
        print(response.choices[0].message.content)

    except Exception as e:
        print(f"Произошла ошибка при обращении к API: {e}")


if __name__ == "__main__":
    check_model()
