import json
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

rows = [json.loads(l) for l in Path("data/processed/chunks_kept.jsonl").open(encoding="utf-8")]
vecs = np.load("data/processed/embeddings.npy")
model = SentenceTransformer("all-MiniLM-L6-v2")

q = " ".join(sys.argv[1:]) or "What is the attendance requirement?"
qv = model.encode([q], normalize_embeddings=True)[0]
scores = vecs @ qv  # cosine similarity (vectors are normalized)

for i in np.argsort(-scores)[:3]:
    r = rows[i]
    print(f"\n[{scores[i]:.2f}] {r['source']} p.{r['page']}\n{r['text'][:400]}")