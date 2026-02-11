import os
import requests
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

def test_proxy():
    load_dotenv()
    proxy_url = os.getenv("TINYPROXY_URL")
    print(f"Using Proxy URL: {proxy_url}")
    
    proxies = {
        "http": proxy_url,
        "https": proxy_url
    }
    
    try:
        print("\n--- Testing Egress IP ---")
        resp = requests.get("https://ifconfig.me/all.json", proxies=proxies, timeout=10)
        data = resp.json()
        print(f"Egress IP: {data.get('ip_addr')}")
        print(f"Remote Host: {data.get('remote_host')}")
        print(f"User Agent: {data.get('user_agent')}")
    except Exception as e:
        print(f"Error checking egress IP: {e}")

async def test_gemini():
    load_dotenv()
    proxy_url = os.getenv("TINYPROXY_URL")
    if proxy_url:
        os.environ["HTTP_PROXY"] = proxy_url
        os.environ["HTTPS_PROXY"] = proxy_url
    
    api_key = os.getenv("GEMINI_API_KEY")
    base_url = os.getenv("PROXYAPI_BASE_URL")
    
    print("\n--- Testing Gemini Connection ---")
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                api_version="v1beta",
                base_url=base_url if base_url else None
            )
        )
        
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents="Say 'Proxy Connection Successful' in English."
        )
        print(f"Gemini Response: {response.text}")
    except Exception as e:
        print(f"Error connecting to Gemini: {e}")

if __name__ == "__main__":
    test_proxy()
    asyncio.run(test_gemini())
