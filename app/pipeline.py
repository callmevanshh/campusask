import os
import re

from app.llm import generate
from app.retrieval import search

LITE = os.getenv("LITE") == "1"
SEM_MIN = 0.40
KW_MIN = float(os.getenv("KW_MIN", "6"))  # tune karenge (step 3)
REFUSAL = "I could not find this in the documents."
_cache = {}


def _relevant(chunks):
    if LITE:
        return max(c["kw"] for c in chunks) >= KW_MIN
    return max(c["sem"] for c in chunks) >= SEM_MIN

def answer(question: str) -> dict:
    key = " ".join(question.lower().split())
    if key in _cache:
        return _cache[key]

    chunks = search(question, k=4)
    if not chunks or not _relevant(chunks):
        return {"answer": REFUSAL, "sources": []}

    text = generate(question, chunks)
    if REFUSAL in text:
        result = {"answer": REFUSAL, "sources": []}
    else:
        cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
        sources = [
            {"n": i, "source": c["source"], "page": c["page"], "text": c["text"]}
            for i, c in enumerate(chunks, 1)
            if not cited or i in cited
        ]
        result = {"answer": text, "sources": sources}

    if len(_cache) > 500:
        _cache.clear()
    _cache[key] = result
    return result