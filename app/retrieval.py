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
    return (r.get("section", "") + " " + r["text"]).strip()

STOP = {"the", "a", "an", "is", "are", "was", "were", "am", "of", "to", "in", "and", "or", "what",
        "if", "i", "my", "me", "we", "you", "your", "for", "on", "do", "does", "how", "can", "be",
        "it", "that", "this", "with", "get", "tell", "about", "please", "explain", "give", "there",
        "any", "will", "would", "should", "which", "who", "when", "where", "why", "at", "by",
        "from", "as", "so", "also", "want", "know", "much", "many"}

SYNONYMS = {"sem": "semester", "sems": "semester", "honour": "honor", "honours": "honor",
            "intern": "internship", "interns": "internship", "gpa": "cgpa", "uni": "university"}
EXPAND = {"backlog": ["fail", "repeat"], "backlogs": ["fail", "repeat"],
          "criteria": ["requirements"], "criterion": ["requirements"],
          "long": ["duration"], "length": ["duration"]}

def _normalize(text):
    text = text.lower()
    text = re.sub(r"\bb\.?\s?tech\b", "btech", text)
    text = re.sub(r"\bm\.?\s?tech\b", "mtech", text)
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
    out = []
    for w in _words(text):
        w = SYNONYMS.get(w, w)
        out.extend(EXPAND.get(w, []))
        out.append(_fix(w))
    return [_stem(w) for w in out]


_bm25 = BM25Okapi([_tok_doc(_doc_text(r)) for r in _rows])

if not LITE:
    from sentence_transformers import SentenceTransformer

    _vecs = np.load(DATA / "embeddings.npy")
    _model = SentenceTransformer("all-MiniLM-L6-v2")


BRANCHES = {"cse", "csai", "csam", "csd", "csss", "csb", "ece", "eve", "csecon"}
BRANCH_W = float(os.getenv("BRANCH_W", "0.5"))
_branch_of = [r["source"].split("-")[0].lower() if r["source"].split("-")[0].lower() in BRANCHES else None
              for r in _rows]


def _scope_weights(query):
    mentioned = {w for w in re.findall(r"[a-z]+", query.lower()) if w in BRANCHES}
    w = np.ones(len(_rows))
    for i, b in enumerate(_branch_of):
        if b is None:
            continue
        w[i] = (1.0 if b in mentioned else BRANCH_W * 0.7) if mentioned else BRANCH_W
    return w


def search(query, k=4, mode="hybrid"):
    w = _scope_weights(query)
    kw = _bm25.get_scores(_tok_query(query))
    kw_rank = [int(i) for i in np.argsort(-(kw * w))[:20] if kw[i] > 0]

    if LITE or mode == "keyword":
        return [{**_rows[i], "sem": 0.0, "kw": float(kw[i])} for i in kw_rank[:k]]

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
        order = sorted(fused, key=fused.get, reverse=True)[:k]

    return [{**_rows[i], "sem": float(sem[i]), "kw": float(kw[i])} for i in order]