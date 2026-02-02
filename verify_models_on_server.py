import os
import asyncio
from google import genai
from dotenv import load_dotenv

load_dotenv()

async def verify_models():
    proxyapi_key = os.getenv("PROXYAPI_KEY")
    proxyapi_base_url = os.getenv("PROXYAPI_BASE_URL")
    
    print(f"Using Proxy: {proxyapi_base_url}")
    
    client = genai.Client(
        api_key=proxyapi_key,
        http_options={'base_url': proxyapi_base_url}
    )
    
    models_to_test = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash-lite-preview-02-05"
    ]
    
    for model_name in models_to_test:
        print(f"\nTesting model {model_name}...")
        try:
            response = await client.aio.models.generate_content(
                model=model_name,
                contents='Say "Hello" in Russian'
            )
            print(f"✓ Success: {response.text}")
        except Exception as e:
            print(f"✗ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_models())
