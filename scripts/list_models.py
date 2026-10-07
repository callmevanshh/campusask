import os

import httpx
from dotenv import load_dotenv

load_dotenv()
r = httpx.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    headers={"x-goog-api-key": os.getenv("GEMINI_API_KEY")},
    timeout=30,
)
r.raise_for_status()
for m in r.json().get("models", []):
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(m["name"])