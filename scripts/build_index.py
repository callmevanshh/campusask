import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

rows = [json.loads(l) for l in Path("data/processed/chunks.jsonl").open(encoding="utf-8") if l.strip()]
Path("data/processed/chunks_kept.jsonl").write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
print("chunks:", len(rows))

model = SentenceTransformer("all-MiniLM-L6-v2")
texts = [(r["section"] + ". " + r["text"]) if r.get("section") else r["text"] for r in rows]
vecs = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
np.save("data/processed/embeddings.npy", vecs)
print("embeddings shape:", vecs.shape)