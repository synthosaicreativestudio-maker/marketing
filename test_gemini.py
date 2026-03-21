import os
import requests

API_KEY = "AIzaSyD5WGVM1AqIjhszcGEprqOo-PwrldExmQs"
PROXIES = {
    "http": "http://127.0.0.1:10809",
    "https": "http://127.0.0.1:10809"
}

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
payload = {
    "contents": [{"parts": [{"text": "Say Hello!"}]}]
}

try:
    print("Sending request to Gemini via Proxy (127.0.0.1:10809)...")
    resp = requests.post(url, json=payload, proxies=PROXIES, timeout=15)
    print("Status:", resp.status_code)
    print("Response:", resp.text)
except Exception as e:
    print("Error:", e)
