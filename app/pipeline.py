import os
import re

import httpx

from app.llm import generate
from app.retrieval import search

LITE = os.getenv("LITE") == "1"
SEM_MIN = 0.40
KW_MIN = float(os.getenv("KW_MIN", "2"))
REFUSAL = "I could not find this in the documents."
_cache = {}

GREET = {"hi", "hii", "hiii", "hello", "helo", "hey", "heya", "hola", "yo", "namaste", "hi hello", "hello hi"}
THANKS = {"thanks", "thank you", "thx", "ty", "thanks a lot", "thank you so much", "shukriya", "dhanyavad"}
ACK = {"ok", "okay", "cool", "nice", "great", "got it", "acha", "accha", "theek hai", "thik hai"}
ABOUT = {"who are you", "what are you", "what can you do", "help", "how do you work", "what do you do"}

FOLLOWUP = re.compile(
    r"\b(?:it|its|that|this|those|these|they|them|there|same|above|earlier|also|iska|uska|isme|usme|aur)\b"
    r"|^\s*(?:and|then|what about|how about|just|only|elaborate|simplify|summari[sz]e|shorter|in detail|in a table|as a table|more detail)\b", re.I)


def _smalltalk(q):
    t = re.sub(r"\b(campusask|campus ask|bro|bhai|sir|buddy|dude|yaar|there)\b", " ", q.lower())
    t = " ".join(re.sub(r"[^a-z ]", " ", t).split())
    if t in GREET or re.fullmatch(r"good (morning|afternoon|evening)", t):
        return ("Hi! I answer questions about IIIT Delhi academic rules using the official documents. "
                "Try attendance, grading, semester leave, internships, or your branch's courses. "
                "Pick your program at the top for branch-specific answers.")
    if t in THANKS:
        return "You're welcome! Ask me anything else about the academic rules."
    if t in ACK:
        return "Okay. Ask me anything else about the academic rules whenever you like."
    if t in ABOUT:
        return ("I'm CampusAsk, an unofficial assistant for IIIT Delhi academic rules. I search the official "
                "regulations and show the exact source so you can verify every answer. I can't answer things "
                "these documents don't cover.")
    return None


def _relevant(chunks):
    if LITE:
        return max(c["kw"] for c in chunks) >= KW_MIN
    return max(c["sem"] for c in chunks) >= SEM_MIN


def _passages(chunks):
    out = []
    for i, c in enumerate(chunks, 1):
        url = c.get("url")
        web = c.get("kind") == "web"
        out.append({
            "n": i, "source": c["source"], "title": c.get("title", c["source"]),
            "version": c.get("version", ""), "section": c.get("section", ""),
            "page": None if web else c["page"], "text": c["text"],
            "url": (url if web else f"{url}#page={c['page']}") if url else None,
        })
    return out


def answer(question: str, history=None, branch: str = "") -> dict:
    small = _smalltalk(question)
    if small:
        return {"answer": small, "sources": []}

    branch = (branch or "").strip().lower()
    use_hist = bool(history) and bool(FOLLOWUP.search(question))
    search_q = question
    if use_hist:
        last_user = next((t["text"] for t in reversed(history) if t["role"] == "user"), "")
        search_q = f"{last_user} {question}".strip()

    key = branch + "|" + " ".join(question.lower().split())
    if not use_hist and key in _cache:
        return _cache[key]

    chunks = search(search_q, k=6, branch=branch)
    print(f"[ask] q={question!r} branch={branch!r} followup={use_hist} "
          f"src={[c['source'].split('-')[0] + ':p' + str(c['page']) for c in chunks]} "
          f"kw={[round(c['kw'], 1) for c in chunks]}")
    if not chunks or not _relevant(chunks):
        print("[ask] refused by relevance gate")
        return {"answer": REFUSAL, "sources": []}

    try:
        text = generate(question, chunks, history if use_hist else None, branch)
    except httpx.HTTPError as e:
        print("LLM ERROR:", repr(e))
        return {
            "answer": "The AI summary is unavailable right now (usage limit reached). "
                      "Here are the most relevant passages from the official documents:",
            "sources": _passages(chunks),
        }

    cited = {int(n) for grp in re.findall(r"\[([\d,\s]+)\]", text) for n in re.findall(r"\d+", grp)}
    if text.strip().startswith(REFUSAL):
        print("[ask] refused by LLM")
        result = {"answer": REFUSAL, "sources": []}
    elif not cited:
        print("[ask] reply had no citations, treated as not found")
        result = {"answer": REFUSAL, "sources": []}
    else:
        result = {"answer": text, "sources": [s for s in _passages(chunks) if s["n"] in cited]}

    if not use_hist:
        if len(_cache) > 500:
            _cache.clear()
        _cache[key] = result
    return result