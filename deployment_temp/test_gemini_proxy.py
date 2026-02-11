#!/usr/bin/env python3
"""
Тестовый скрипт для проверки доступа к Gemini API через ProxyAPI.ru
Использование: python test_gemini_proxy.py
"""
import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()


async def test_gemini_access():
    """Тестирование доступа к Gemini API через прокси."""
    proxyapi_key = os.getenv("PROXYAPI_KEY")
    proxyapi_base_url = os.getenv("PROXYAPI_BASE_URL")
    gemini_key = os.getenv("GEMINI_API_KEY")
    http_proxy = os.getenv("HTTP_PROXY")
    https_proxy = os.getenv("HTTPS_PROXY")
    
    print("=" * 60)
    print("ПРОВЕРКА КОНФИГУРАЦИИ GEMINI API")
    print("=" * 60)
    
    print(f"PROXYAPI_KEY: {'✓ установлен' if proxyapi_key else '✗ отсутствует'}")
    print(f"PROXYAPI_BASE_URL: {proxyapi_base_url or '✗ отсутствует'}")
    print(f"GEMINI_API_KEY: {'✓ установлен' if gemini_key else '✗ отсутствует'}")
    print(f"HTTP_PROXY: {http_proxy or '✗ отсутствует'}")
    print(f"HTTPS_PROXY: {https_proxy or '✗ отсутствует'}")
    
    print("\n" + "=" * 60)
    print("ТЕСТ ЗАПРОСА К GEMINI API")
    print("=" * 60)
    
    try:
        # Вариант Б: Прямое использование ProxyAPI
        if proxyapi_key and proxyapi_base_url:
            print("Режим: ProxyAPI (прямая замена URL)")
            client = genai.Client(
                api_key=proxyapi_key,
                http_options={'api_endpoint': proxyapi_base_url}
            )
        # Вариант А: Стандартный API с HTTP_PROXY
        elif gemini_key:
            print("Режим: Стандартный API" + (" + HTTP_PROXY" if http_proxy else ""))
            client = genai.Client(api_key=gemini_key)
        else:
            print("✗ ОШИБКА: Не найден ни один ключ API")
            return False
        
        print("Отправка тестового запроса к модели gemini-3-pro-preview...")
        
        response = await client.aio.models.generate_content(
            model='gemini-3-pro-preview',
            contents='Скажи "привет" в одном слове на русском языке'
        )
        
        print("\n" + "=" * 60)
        print("✓ УСПЕХ!")
        print("=" * 60)
        print(f"Ответ модели: {response.text}")
        print("=" * 60)
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("✗ ОШИБКА ДОСТУПА К API")
        print("=" * 60)
        print(f"Тип ошибки: {type(e).__name__}")
        print(f"Сообщение: {str(e)}")
        print("\nВозможные причины:")
        print("1. Неверный API ключ")
        print("2. Проблемы с прокси-сервером")
        print("3. Региональная блокировка (нужен ProxyAPI)")
        print("4. Проблемы с сетью")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_gemini_access())
    exit(0 if success else 1)
