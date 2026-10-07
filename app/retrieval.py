import json
import os
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

LITE = os.getenv("LITE") == "1"
DATA = Path("data/processed")
_rows = [json.loads(l) for l in (DATA / "chunks_kept.jsonl").open(encoding="utf-8")]

STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "and", "or", "what", "if", "i", "my",
        "for", "on", "do", "does", "how", "can", "be", "it", "that", "this", "with", "get"}


def _tok(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


_bm25 = BM25Okapi([_tok(r["text"]) for r in _rows])

if not LITE:
    from sentence_transformers import SentenceTransformer

    _vecs = np.load(DATA / "embeddings.npy")
    _model = SentenceTransformer("all-MiniLM-L6-v2")


def search(query, k=4, mode="hybrid"):
    kw = _bm25.get_scores(_tok(query))
    kw_rank = [int(i) for i in np.argsort(-kw)[:20] if kw[i] > 0]

    if LITE or mode == "keyword":
        return [{**_rows[i], "sem": 0.0, "kw": float(kw[i])} for i in kw_rank[:k]]

    qv = _model.encode([query], normalize_embeddings=True)[0]
    sem = _vecs @ qv
    sem_rank = [int(i) for i in np.argsort(-sem)[:20]]

    if mode == "semantic":
        order = sem_rank[:k]
    else:  # hybrid: reward chunks that rank well in both lists
        fused = {}
        for ranking in (sem_rank, kw_rank):
            for pos, i in enumerate(ranking):
                fused[i] = fused.get(i, 0) + 1 / (60 + pos + 1)
        order = sorted(fused, key=fused.get, reverse=True)[:k]

    return [{**_rows[i], "sem": float(sem[i]), "kw": float(kw[i])} for i in order]