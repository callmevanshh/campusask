import os
import time
import httpx
from dotenv import load_dotenv

load_dotenv()

SYSTEM = (
    "You are CampusAsk, an assistant for IIIT Delhi students. Answer using ONLY the numbered sources below. "
    "Students write informally, with typos and abbreviations, so match the meaning of the question to the sources, not the exact words. "
    "If the sources contain relevant information, answer helpfully: state the rule first, then the conditions or exceptions, in 2 to 6 sentences (use bullet points if there are several conditions). "
    "The sources may come from different documents (UG regulations, ordinances, and branch-specific regulations such as CSE or CSB). If the answer differs between branches, say which branch each rule applies to. If the question depends on the student's branch and none is mentioned, give the general UG rule and say the branch regulations may differ. "
    "Cite sources like [1] after each claim, one number per bracket. "
    "If the sources only partly answer the question, say what they cover and what is missing. "
    "When useful, name the document and its version the rule comes from (for example 'According to the UG Regulations (Oct 2025)...'). "
    "Only if the sources contain nothing relevant, reply exactly: 'I could not find this in the documents.' "
    "Never use outside knowledge and never invent numbers or rules."
)


def generate(question, chunks):
    key, model = os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL")
    if not key or not model:
        raise RuntimeError("Set GEMINI_API_KEY and GEMINI_MODEL in .env")
    context = "\n\n".join(
        f"[{i+1}] ({c.get('title', c['source'])}, {c.get('version') or 'n/a'}, "
        f"section: {c.get('section') or 'n/a'}, page {c['page']})\n{c['text']}"
        for i, c in enumerate(chunks)
    )
    prompt = f"{SYSTEM}\n\nSOURCES:\n{context}\n\nQUESTION: {question}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}}
    for attempt in range(4):
        r = httpx.post(url, headers={"x-goog-api-key": key}, json=payload, timeout=60)
        if r.status_code in (429, 503) and attempt < 3:
            time.sleep(15 * (attempt + 1))  # wait and try again
            continue
        r.raise_for_status()
        break
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)