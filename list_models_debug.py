
import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()

async def list_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("No API Key found")
        return

    client = genai.Client(api_key=api_key)
    
    print("Listing models...")
    try:
        # Pager for list_models
        async for model in await client.aio.models.list(config={'page_size': 100}):
            print(f"Model: {model.name}")
            # print(f"  Display Name: {model.display_name}")
            # print(f"  Supported Actions: {model.supported_generation_methods}")
            print("-" * 20)
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
