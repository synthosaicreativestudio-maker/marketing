import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Ключ берется из .env (переменная OPENROUTER_API_KEY)
# Для теста можно подставить напрямую, если в .env еще нет
api_key = os.getenv("OPENROUTER_API_KEY", "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")

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=api_key,
  default_headers={
    "HTTP-Referer": "https://github.com/synthosaicreativestudio-maker/marketingbot", # Опционально
    "X-Title": "MarketingBot", # Опционально
  }
)

def test_deepseek():
    try:
        print("--- Тест OpenRouter: DeepSeek R1 ---")
        model = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1")
        print(f"Используемая модель: {model}")
        
        completion = client.chat.completions.create(
          model=model,
          messages=[
            {
              "role": "user",
              "content": "Привет! Напиши короткий слоган для агентства недвижимости, которое использует ИИ."
            }
          ]
        )
        
        print("\n--- Ответ получен ---")
        print(completion.choices[0].message.content)
        print("-----------------------")
        
    except Exception as e:
        print(f"\n❌ Ошибка при запросе: {e}")

if __name__ == "__main__":
    test_deepseek()
