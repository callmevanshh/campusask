import re

from app.llm import generate
from app.retrieval import search

SEM_MIN = 0.40
REFUSAL = "I could not find this in the documents."
_cache = {}


def answer(question: str) -> dict:
    key = " ".join(question.lower().split())
    if key in _cache:
        return _cache[key]

    chunks = search(question, k=4)
    if not chunks or max(c["sem"] for c in chunks) < SEM_MIN:
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