import os
import re

import httpx

from app.llm import generate
from app.retrieval import search

LITE = os.getenv("LITE") == "1"
SEM_MIN = 0.40
KW_MIN = float(os.getenv("KW_MIN", "4"))
REFUSAL = "I could not find this in the documents."
_cache = {}

DOC_URLS = {
    "UG-Regulations-2025-Oct.pdf": "https://iiitd.ac.in/sites/default/files/docs/education/2025/2025-October-UG%20Regulations.pdf",
    "BTech-Ordinances.pdf": "https://iiitd.ac.in/sites/default/files/docs/education/BTech-Ordinances.pdf",
}


def _relevant(chunks):
    if LITE:
        return max(c["kw"] for c in chunks) >= KW_MIN
    return max(c["sem"] for c in chunks) >= SEM_MIN


def _passages(chunks):
    out = []
    for i, c in enumerate(chunks, 1):
        base = DOC_URLS.get(c["source"])
        out.append({
            "n": i, "source": c["source"], "page": c["page"], "text": c["text"],
            "url": f"{base}#page={c['page']}" if base else None,
        })
    return out


def answer(question: str) -> dict:
    key = " ".join(question.lower().split())
    if key in _cache:
        return _cache[key]

    chunks = search(question, k=4)
    print(f"[ask] q={question!r} pages={[c['page'] for c in chunks]} kw={[round(c['kw'], 1) for c in chunks]}")
    if not chunks or not _relevant(chunks):
        print("[ask] refused by relevance gate")
        return {"answer": REFUSAL, "sources": []}

    try:
        text = generate(question, chunks)
    except httpx.HTTPError as e:
        print("LLM ERROR:", repr(e))
        return {
            "answer": "The AI summary is unavailable right now (usage limit reached). Here are the most relevant passages from the official documents:",
            "sources": _passages(chunks),
        }

    if text.strip().startswith(REFUSAL):
        print("[ask] refused by LLM")
        result = {"answer": REFUSAL, "sources": []}
    else:
        cited = {int(n) for grp in re.findall(r"\[([\d,\s]+)\]", text) for n in re.findall(r"\d+", grp)}
        sources = [s for s in _passages(chunks) if not cited or s["n"] in cited]
        result = {"answer": text, "sources": sources}

    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = result
    return result