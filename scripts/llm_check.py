import os

import httpx
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
names = [os.getenv("GEMINI_MODEL")] + [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()]
for m in names:
    try:
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                       headers={"x-goog-api-key": key}, timeout=30,
                       json={"contents": [{"parts": [{"text": "Reply with the single word: ready"}]}]})
        txt = ""
        if r.status_code == 200:
            parts = r.json()["candidates"][0]["content"]["parts"]
            txt = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()[:60]
        print(f"{m}: HTTP {r.status_code} {txt!r}")
    except Exception as e:
        print(f"{m}: {e!r}")