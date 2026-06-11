import os
import requests

api_key = None
# Directly parse .env file
if os.path.exists(".env"):
    with open(".env", "r") as f:
        for line in f:
            if line.startswith("GEMINI_API_KEY="):
                api_key = line.split("=")[1].strip()
                break

if not api_key:
    print("API Key not found in .env file!")
    exit(1)

print(f"Testing API key: {api_key[:10]}...")

# 1. Try listing models
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
try:
    response = requests.get(url)
    print(f"List Models Status: {response.status_code}")
    if response.status_code == 200:
        models = response.json().get("models", [])
        print("\nAvailable models:")
        for m in models:
            name = m.get("name")
            supported_methods = m.get("supportedGenerationMethods", [])
            print(f" - {name} (Methods: {supported_methods})")
    else:
        print(f"Error listing models: {response.text}")
except Exception as e:
    print(f"Exception listing models: {e}")
