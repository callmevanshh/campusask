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
ABOUT = {"who are you", "what are you", "what can you do", "help", "how do you work", "what do you do",
         "can u answer me", "can you answer me", "are you", "hello are you", "hi are you", "test", "testing"}

BRANCH_RE = re.compile(r"\b(csecon|csai|csam|csss|cse|csd|csb|ece|eve)\b", re.I)
TOPIC_STOP = {"for", "in", "of", "the", "i", "am", "im", "m", "from", "branch", "program", "programme", "my",
              "is", "its", "it", "a", "an", "and", "what", "about", "how", "bro", "bhai", "please", "pls",
              "tell", "me", "only", "just", "also", "are", "do", "does", "can", "u", "you", "to", "on", "at",
              "with", "make", "show", "give", "create", "now", "then", "ok", "okay"}
FORMAT_ONLY = {"table", "tabular", "list", "format", "bullet", "bullets", "points", "detail", "detailed",
               "short", "brief", "summary", "summarize", "summarise", "explain", "again", "more", "simple",
               "simplify", "shorter", "elaborate", "clearly", "properly"}
NOT_TOPIC = TOPIC_STOP | FORMAT_ONLY
ORD = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|1st|2nd|3rd|4th|5th|6th|7th|8th|[1-8])"
NEEDS_BRANCH = re.compile(
    rf"\b{ORD}\s*sem(?:ester)?s?\b.*\b(?:courses?|subjects?)\b"
    rf"|\b(?:courses?|subjects?)\b.*\b{ORD}\s*sem(?:ester)?s?\b"
    r"|\bsem(?:ester)?s?[\s\-]*wise\b|\bcurriculum\b|\bprogram structure\b|\bsyllabus\b", re.I)
FOLLOWUP = re.compile(
    r"\b(?:it|its|that|this|those|these|they|them|there|same|above|earlier|also|iska|uska|isme|usme|aur)\b"
    r"|^\s*(?:and|then|what about|how about|just|only|elaborate|simplify|summari[sz]e|shorter|in detail|in a table|as a table|more detail)\b",
    re.I)

# the student talks about themselves
PERSONAL = re.compile(r"\b(?:i|i'm|im|my|mera|meri|mere|maine)\b", re.I)
STATEMENT = re.compile(r"^\s*(?:i|i'm|im|my|mera|meri|maine|main)\b", re.I)
ASKING = re.compile(
    r"\?|\b(?:what|how|can|could|will|would|should|which|when|where|why|who|kya|kitna|kitne|kab|kaise|kyun|"
    r"batao|tell|explain|list|show|eligible|allowed)\b", re.I)

NOTED = ("Noted. What would you like to know? For example: whether your credits or CGPA meet a requirement, "
         "how much course load you can take, or Honors/Minor eligibility.")
CLARIFY = ("Which program are you in? Course lists differ by program (CSE, CSAI, CSAM, CSD, CSSS, CSB, ECE, EVE, CSECON). "
           "Just tell me, for example: \"for CSB\".")
PLANNING = re.compile(r"\b(?:sgpa|cgpa|gpa)\b.*\b(?:need|needed|require[d]?|should|reach|touch|minimum)\b"
                      r"|\b(?:need|should|minimum)\b.*\b(?:sgpa|cgpa|grade)\b", re.I)
PLAN_EXTRA = " grading scheme letter grade points CGPA SGPA"
LEAK = re.compile(r"do not assume that credits|unless the sources say so|never carry over|answer only the new question|"
                  r"for each semester in the student's plan|double-check the comparison|required sgpa = \(|"
                  r"do not multiply the required|never ask for individual|count only credits from courses", re.I)


def _smalltalk(q):
    t = re.sub(r"\b(campusask|campus ask|bro|bhai|sir|buddy|dude|yaar|there)\b", " ", q.lower())
    t = " ".join(re.sub(r"[^a-z ]", " ", t).split())
    if t in GREET or re.fullmatch(r"good (morning|afternoon|evening)", t):
        return ("Hi! I answer questions about IIIT Delhi academic rules using the official documents. "
                "Try attendance, grading, semester leave, internships, or your branch's courses. "
                "Mention your program (for example CSB) for branch-specific answers.")
    if t in THANKS:
        return "You're welcome! Ask me anything else about the academic rules."
    if t in ACK:
        return "Okay. Ask me anything else about the academic rules whenever you like."
    if t in ABOUT:
        return ("I'm CampusAsk, an unofficial assistant for IIIT Delhi academic rules. I search the official "
                "regulations and show the exact source so you can verify every answer. Ask me a question about "
                "attendance, grading, leave, internships or your program's courses.")
    return None


def _statement_only(q):
    """'i have cgpa of 4.95 in 7th sem': facts about the student but no question."""
    return bool(STATEMENT.match(q)) and not ASKING.search(q) and bool(re.search(r"\d", q))


def _branch_in(text):
    found = BRANCH_RE.findall(text or "")
    return found[-1].lower() if found else ""


def _branch_from_chat(history):
    for t in reversed(history or []):
        if t["role"] == "user":
            b = _branch_in(t["text"])
            if b:
                return b
    return ""


def _topic_words(text):
    stripped = " ".join(BRANCH_RE.sub(" ", text or "").split())
    return stripped, [w for w in re.findall(r"[a-z]+", stripped.lower()) if w not in NOT_TOPIC]


def _topic(history):
    for t in reversed(history or []):
        if t["role"] != "user":
            continue
        stripped, words = _topic_words(t["text"])
        if len(words) >= 2:
            return stripped
    return ""


def _is_followup(q, history):
    if not history:
        return False
    last_a = next((t["text"] for t in reversed(history) if t["role"] == "assistant"), "")
    if "?" in last_a[-200:] and len(last_a) <= 400 and len(q.split()) <= 12 and not ASKING.search(q):
        return True  # the student is answering a question the bot just asked
    _, words = _topic_words(q)
    if len(words) >= 5:
        return False  # a full question with its own topic is never merged with the previous one
    if FOLLOWUP.search(q):
        return True
    return len(words) == 0 and len(q.split()) <= 6  # "for cse", "CSB", "table ?", "make a table"

def resolve(question, history=None, branch=""):
    small = _smalltalk(question)
    if small:
        return {"reply": small}
    if _statement_only(question):
        return {"reply": NOTED}
    branch = _branch_in(question) or (branch or "").strip().lower() or _branch_from_chat(history)
    if not branch and len(question.split()) <= 14 and NEEDS_BRANCH.search(question):
        return {"reply": CLARIFY}
    use_hist = _is_followup(question, history)
    topic = _topic(history) if use_hist else ""
    search_q = f"{topic} {question}".strip() if topic else question
    return {"branch": branch, "search_q": search_q, "use_hist": use_hist,
            "personal": bool(PERSONAL.search(question)),
            "extra": PLAN_EXTRA if PLANNING.search(search_q) else ""}


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

def _scrub(text):
    """Drop any line in which the model repeated one of its own instructions."""
    return "\n".join(ln for ln in text.split("\n") if not LEAK.search(ln)).strip()

def _plain_math(text):
    """The UI does not render LaTeX, so turn $...$ and common commands into plain text."""
    text = re.sub(r"\\text\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\$\$?([^$\n]+)\$\$?", r"\1", text)
    for a, b in (("\\min", "min"), ("\\max", "max"), ("\\times", "x"), ("\\cdot", "x"), ("\\leq", "<="),
                 ("\\geq", ">="), ("\\le", "<="), ("\\ge", ">="), ("\\{", "{"), ("\\}", "}")):
        text = text.replace(a, b)
    return text

def answer(question: str, history=None, branch: str = "") -> dict:
    r = resolve(question, history, branch)
    if "reply" in r:
        return {"answer": r["reply"], "sources": []}
    branch, search_q, use_hist, personal = r["branch"], r["search_q"], r["use_hist"], r["personal"]
    with_hist = use_hist or (personal and bool(history))

    key = branch + "|" + " ".join(question.lower().split())
    if not with_hist and key in _cache:
        return _cache[key]

    chunks = search(search_q + r["extra"], k=8 if personal else 6, branch=branch)
    print(f"[ask] q={question!r} resolved={search_q!r} branch={branch!r} followup={use_hist} personal={personal} "
          f"src={[c['source'].split('-')[0] + ':p' + str(c['page']) for c in chunks]} "
          f"kw={[round(c['kw'], 1) for c in chunks]}")
    if not chunks or not _relevant(chunks):
        print("[ask] refused by relevance gate")
        return {"answer": REFUSAL, "sources": []}

    hist = None
    if with_hist:
        # follow-ups need the earlier answers; a fresh personal question only needs the facts the student stated
        hist = history if use_hist else [t for t in history if t["role"] == "user"][-6:]
    try:
        text = generate(search_q, chunks, hist, branch)
    except httpx.HTTPError as e:
        print("LLM ERROR:", repr(e))
        return {
            "answer": "The AI summary is unavailable right now (usage limit reached). "
                      "Here are the most relevant passages from the official documents:",
            "sources": _passages(chunks),
        }

    if text.strip().upper().startswith("CLARIFY:"):
        return {"answer": text.strip()[8:].strip(), "sources": []}
    
    text = _plain_math(_scrub(text))
    cited = {int(n) for grp in re.findall(r"\[([\d,\s]+)\]", text) for n in re.findall(r"\d+", grp)}
    if text.strip().startswith(REFUSAL):
        print("[ask] refused by LLM")
        result = {"answer": REFUSAL, "sources": []}
    elif not cited:
        print("[ask] reply had no citations, treated as not found")
        result = {"answer": REFUSAL, "sources": []}
    else:
        result = {"answer": text, "sources": [s for s in _passages(chunks) if s["n"] in cited]}

    if not with_hist:
        if len(_cache) > 500:
            _cache.clear()
        _cache[key] = result
    return result