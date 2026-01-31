import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY", "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")

def list_models():
    try:
        print("--- Запрос списка моделей OpenRouter ---")
        response = requests.get("https://openrouter.ai/api/v1/models")
        if response.status_code == 200:
            models = response.json().get('data', [])
            deepseek_models = [m['id'] for m in models if 'deepseek' in m['id'].lower()]
            print(f"Найдено моделей DeepSeek: {len(deepseek_models)}")
            for model_id in deepseek_models:
                print(f" - {model_id}")
        else:
            print(f"Ошибка {response.status_code}: {response.text}")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    list_models()
