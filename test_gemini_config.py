import os
import asyncio
from dotenv import load_dotenv
from google import genai

async def test_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL")
    proxy_url = os.getenv("PROXYAPI_BASE_URL")
    
    print(f"Testing Gemini with model: {model_name}")
    
    if proxy_url:
        print(f"Using proxy: {proxy_url}")
        client = genai.Client(
            api_key=api_key,
            http_options={
                'base_url': proxy_url,
                'api_version': 'v1beta'
            }
        )
    else:
        client = genai.Client(api_key=api_key)
        
    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents="Hello, this is a test from Antigravity. Just respond with 'Connection OK'."
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
