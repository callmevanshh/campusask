import os

import httpx
from dotenv import load_dotenv

load_dotenv()

SYSTEM = (
    "You answer questions about IIIT Delhi academic rules using ONLY the numbered sources below. "
    "Cite sources like [1] after each claim. If the sources do not contain the answer, reply exactly: "
    "'I could not find this in the documents.' Never use outside knowledge. Be concise."
)


def generate(question, chunks):
    key, model = os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL")
    if not key or not model:
        raise RuntimeError("Set GEMINI_API_KEY and GEMINI_MODEL in .env")
    context = "\n\n".join(
        f"[{i+1}] ({c['source']}, page {c['page']})\n{c['text']}" for i, c in enumerate(chunks)
    )
    prompt = f"{SYSTEM}\n\nSOURCES:\n{context}\n\nQUESTION: {question}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    r = httpx.post(
        url,
        headers={"x-goog-api-key": key},
        json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}},
        timeout=60,
    )
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)