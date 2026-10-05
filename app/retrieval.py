import json
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

DATA = Path("data/processed")
_rows = [json.loads(l) for l in (DATA / "chunks_kept.jsonl").open(encoding="utf-8")]
_vecs = np.load(DATA / "embeddings.npy")
_model = SentenceTransformer("all-MiniLM-L6-v2")

STOP = {"the", "a", "an", "is", "are", "of", "to", "in", "and", "or", "what", "if", "i", "my",
        "for", "on", "do", "does", "how", "can", "be", "it", "that", "this", "with", "get"}


def _tok(text):
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


_bm25 = BM25Okapi([_tok(r["text"]) for r in _rows])


def search(query, k=4, mode="hybrid"):
    qv = _model.encode([query], normalize_embeddings=True)[0]
    sem = _vecs @ qv
    kw = _bm25.get_scores(_tok(query))
    sem_rank = list(np.argsort(-sem)[:20])
    kw_rank = [i for i in np.argsort(-kw)[:20] if kw[i] > 0]

    if mode == "semantic":
        order = sem_rank[:k]
    elif mode == "keyword":
        order = kw_rank[:k]
    else:  # reciprocal rank fusion: reward chunks that rank well in both lists
        fused = {}
        for ranking in (sem_rank, kw_rank):
            for pos, i in enumerate(ranking):
                fused[i] = fused.get(i, 0) + 1 / (60 + pos + 1)
        order = sorted(fused, key=fused.get, reverse=True)[:k]

    return [{**_rows[i], "sem": float(sem[i]), "kw": float(kw[i])} for i in order]