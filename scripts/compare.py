import sys

from app.retrieval import search

q = " ".join(sys.argv[1:])
for mode in ("semantic", "keyword", "hybrid"):
    print(f"\n== {mode} ==")
    for c in search(q, k=3, mode=mode):
        print(f"  {c['source']} p.{c['page']}")