import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("No API KEY found")
    exit()

client = genai.Client(api_key=api_key)

print("Listing available models (google-genai SDK)...")
try:
    # SDK v1.0
    for m in client.models.list():
        # Filter for models that likely support generateContent
        print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")
