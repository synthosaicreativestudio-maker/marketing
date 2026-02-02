import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env")
    exit(1)

client = genai.Client(api_key=api_key)

try:
    print("Checking available models for your API key:")
    found = False
    for model in client.models.list():
        print(f"- {model.name}")
        if "gemini-3-flash-preview" in model.name:
            found = True
    
    if found:
        print("\nSUCCESS: 'gemini-3-flash-preview' is available!")
    else:
        print("\nWARNING: 'gemini-3-flash-preview' NOT found in the list.")
except Exception as e:
    print(f"Error communicating with Gemini API: {e}")
