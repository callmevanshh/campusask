import difflib
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import snowballstemmer
from rank_bm25 import BM25Okapi

LITE = os.getenv("LITE") == "1"
DATA = Path("data/processed")
_rows = [json.loads(l) for l in (DATA / "chunks_kept.jsonl").open(encoding="utf-8")]
_stem = snowballstemmer.stemmer("english").stemWord
def _doc_text(r):
    t = " ".join(x for x in (r.get("section", ""), r.get("index_extra", ""), r["text"]) if x)
    return t.replace("<br>", " ")

STOP = {"the", "a", "an", "is", "are", "was", "were", "am", "of", "to", "in", "and", "or", "what",
        "if", "i", "my", "me", "we", "you", "your", "for", "on", "do", "does", "how", "can", "be",
        "it", "that", "this", "with", "get", "tell", "about", "please", "explain", "give", "there",
        "any", "will", "would", "should", "which", "who", "when", "where", "why", "at", "by",
        "from", "as", "so", "also", "want", "know", "much", "many"}

SYNONYMS = {"sem": "semester", "sems": "semester", "honour": "honor", "honours": "honor",
            "intern": "internship", "interns": "internship", "gpa": "cgpa", "uni": "university"}
EXPAND = {"backlog": ["fail", "repeat"], "backlogs": ["fail", "repeat"],
          "criteria": ["requirements"], "criterion": ["requirements"],
          "long": ["duration"], "length": ["duration"],
          "plagiarism": ["cheating", "dishonesty"], "plagiarize": ["cheating", "dishonesty"],
          "penalty": ["punishment"], "penalties": ["punishment"], "punishment": ["penalty"]}

_ORD = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"]
ORD_DIGIT = {w: str(i + 1) for i, w in enumerate(_ORD)}


def _normalize(text):
    text = text.lower()
    text = re.sub(r"\bb\.?\s?tech\b", "btech", text)
    text = re.sub(r"\bm\.?\s?tech\b", "mtech", text)
    text = re.sub(r"\b([1-8])(?:st|nd|rd|th)\b", lambda m: _ORD[int(m.group(1)) - 1], text)
    return re.sub(r"(?<=[a-z])\.(?=[a-z])", "", text)


def _words(text):
    return [w for w in re.findall(r"[a-z0-9]+", _normalize(text)) if w not in STOP]


_vocab = {w for r in _rows for w in _words(_doc_text(r))}
_by_first = defaultdict(list)
for _w in sorted(_vocab):
    _by_first[_w[0]].append(_w)


def _fix(w):
    """Correct a typo by matching against words that exist in the documents."""
    if w in _vocab or len(w) < 4 or w.isdigit():
        return w
    m = difflib.get_close_matches(w, _by_first.get(w[0], []), n=1, cutoff=0.8)
    return m[0] if m else w


def _tok_doc(text):
    return [_stem(w) for w in _words(text)]


def _tok_query(text):
    words = _words(text)
    has_sem = any(w in ("semester", "semesters", "sem", "sems") for w in words)
    out = []
    for w in words:
        w = SYNONYMS.get(w, w)
        out.extend(EXPAND.get(w, []))
        if has_sem and w in ORD_DIGIT:
            out.append(ORD_DIGIT[w])  # "first semester" also matches tables headed "Semester 1"
        out.append(_fix(w))
    return [_stem(w) for w in out]


_bm25 = BM25Okapi([_tok_doc(_doc_text(r)) for r in _rows])

if not LITE:
    from sentence_transformers import SentenceTransformer

    _vecs = np.load(DATA / "embeddings.npy")
    _model = SentenceTransformer("all-MiniLM-L6-v2")


BRANCHES = {"cse", "csai", "csam", "csd", "csss", "csb", "ece", "eve", "csecon"}
BRANCH_W = float(os.getenv("BRANCH_W", "0.5"))
NEWEST_BOOST = float(os.getenv("NEWEST_BOOST", "2.5"))
TABLE_BOOST = float(os.getenv("TABLE_BOOST", "2.5"))
CAMPUS_W = float(os.getenv("CAMPUS_W", "0.6"))
YEAR = re.compile(r"\b(?:19|20)\d\d\b|\bbatch\b", re.I)
SWITCHING = re.compile(r"transfer|chang|switch|migrat", re.I)
GENERIC = {_stem(w) for w in ("branch", "program", "programme", "department")}
_O = r"(?:first|second|third|fourth|fifth|sixth|seventh|eighth|1st|2nd|3rd|4th|5th|6th|7th|8th|[1-8])"
CURRICULUM = re.compile(rf"\b{_O}\s*sem(?:ester)?s?\b.*\b(?:courses?|subjects?)\b"
                        rf"|\b(?:courses?|subjects?)\b.*\b{_O}\s*sem(?:ester)?s?\b"
                        r"|\bsem(?:ester)?s?[\s\-]*wise\b|\bcurriculum\b|\bprogram structure\b|\bsyllabus\b", re.I)
# campus-life policies: for generic academic questions they should not crowd out the regulations
CAMPUS_FILES = ("Hostel-", "Final-Hostel", "Fine-", "Student-Conduct", "Policy-against", "Academic-Dishonesty", "Fee-")
CAMPUS_TERMS = {_stem(w) for w in (
    "hostel", "mess", "canteen", "room", "rooms", "warden", "fine", "fines", "penalty", "penalties", "ragging",
    "conduct", "discipline", "disciplinary", "misconduct", "plagiarism", "plagiarize", "cheating", "dishonesty",
    "harassment", "complaint", "complaints", "complain", "grievance", "security", "visitor", "visitors", "curfew",
    "laundry", "wifi", "internet", "fee", "fees", "tuition", "refund", "scholarship", "scholarships", "stipend",
    "allotment", "campus", "behaviour", "behavior", "punishment", "violation", "cab", "driver", "transport",
    "bus", "sports", "gym")}
_branch_of = []
for _r in _rows:
    _b = _r["source"].split("-")[0].lower()
    _branch_of.append(_b if _b in BRANCHES else None)
_newest = np.array([1.0 if r.get("newest") else 0.0 for r in _rows])
_is_table = np.array([bool(r.get("table")) for r in _rows])
_campus = np.array([1.0 if r["source"].startswith(CAMPUS_FILES) else 0.0 for r in _rows])


def _named(query, branch=None):
    named = {w for w in re.findall(r"[a-z]+", query.lower()) if w in BRANCHES}
    if branch and branch.lower() in BRANCHES:
        named.add(branch.lower())
    return named


def _scope_weights(query, branch=None):
    mentioned = _named(query, branch)
    w = np.ones(len(_rows))
    for i, b in enumerate(_branch_of):
        if b is None:
            continue
        w[i] = (1.8 if b in mentioned else 0.15) if mentioned else BRANCH_W
    if not YEAR.search(query) and (mentioned or CURRICULUM.search(query)):
        w = w * np.where(_newest > 0, NEWEST_BOOST, 1.0)
    if mentioned and CURRICULUM.search(query):  # a curriculum question wants that program's table
        for i, b in enumerate(_branch_of):
            if b in mentioned and _is_table[i]:
                w[i] *= TABLE_BOOST
    if not ({_stem(x) for x in _words(query)} & CAMPUS_TERMS):
        w = w * np.where(_campus > 0, CAMPUS_W, 1.0)
    return w


def _query_tokens(query, branch=None):
    toks = _tok_query(query)
    if _named(query, branch) and not SWITCHING.search(query):
        toks = [t for t in toks if t not in GENERIC]
    return toks


MAX_EXTRA = 4


def _first_sec(r):
    return (r.get("section") or "").split(" / ")[0]


def _last_sec(r):
    return (r.get("section") or "").split(" / ")[-1]


def _with_neighbours(order, k):
    out = list(order[:k])
    extra = 0
    for i in list(out):
        j = i + 1
        if extra >= MAX_EXTRA or j >= len(_rows) or j in out:
            continue
        a, b = _rows[i], _rows[j]
        if a["source"] != b["source"] or a.get("table") or b.get("table"):
            continue
        if b["page"] - a["page"] not in (0, 1):
            continue
        if _last_sec(a) and _last_sec(a) == _first_sec(b):
            out.append(j)
            extra += 1
    return out


def search(query, k=4, mode="hybrid", branch=None, expand=True):
    w = _scope_weights(query, branch)
    kw = _bm25.get_scores(_query_tokens(query, branch))
    kw_rank = [int(i) for i in np.argsort(-(kw * w))[:20] if kw[i] > 0]

    if LITE or mode == "keyword":
        order = _with_neighbours(kw_rank, k) if expand else kw_rank[:k]
        return [{**_rows[i], "sem": 0.0, "kw": float(kw[i])} for i in order]

    qv = _model.encode([query], normalize_embeddings=True)[0]
    sem = _vecs @ qv
    sem_rank = [int(i) for i in np.argsort(-(sem * w))[:20]]

    if mode == "semantic":
        order = sem_rank[:k]
    else:
        fused = {}
        for ranking in (sem_rank, kw_rank):
            for pos, i in enumerate(ranking):
                fused[i] = fused.get(i, 0) + 1 / (60 + pos + 1)
        ranked = sorted(fused, key=fused.get, reverse=True)
        order = _with_neighbours(ranked, k) if expand else ranked[:k]

    return [{**_rows[i], "sem": float(sem[i]), "kw": float(kw[i])} for i in order]