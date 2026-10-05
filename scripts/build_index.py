import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

CHUNKS = Path("data/processed/chunks.jsonl")
OUT_VEC = Path("data/processed/embeddings.npy")
EXCLUDE_PAGES = {"UG-Regulations-2025-Oct.pdf": set(range(29, 35))}  # changelog pages

rows = [json.loads(l) for l in CHUNKS.open(encoding="utf-8")]
rows = [r for r in rows if r["page"] not in EXCLUDE_PAGES.get(r["source"], set())]
print("chunks kept:", len(rows))

model = SentenceTransformer("all-MiniLM-L6-v2")  # small, CPU-friendly
vecs = model.encode([r["text"] for r in rows], normalize_embeddings=True, show_progress_bar=True)

np.save(OUT_VEC, vecs)
Path("data/processed/chunks_kept.jsonl").write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
print("embeddings shape:", vecs.shape)