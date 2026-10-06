import json
import sys
from pathlib import Path

from app.retrieval import _rows, search

DEFAULT_SRC = "UG-Regulations-2025-Oct.pdf"
path = sys.argv[1] if len(sys.argv) > 1 else "eval/questions.jsonl"

for n, line in enumerate(Path(path).open(encoding="utf-8"), 1):
    if not line.strip():
        continue
    q = json.loads(line)
    if not q["answerable"]:
        continue
    gold = {(q.get("source", DEFAULT_SRC), p) for p in q["pages"]}
    res = search(q["q"], k=3)
    if any((c["source"], c["page"]) in gold for c in res):
        continue
    print("=" * 80)
    print(f"#{n} {q['q']}  | gold pages: {q['pages']}")
    print("\n-- retrieved --")
    for c in res:
        print(f"[p.{c['page']}] {c['text'][:300]!r}")
    print("\n-- text on gold pages --")
    found = False
    for r in _rows:
        if (r["source"], r["page"]) in gold:
            found = True
            print(f"[p.{r['page']}] {r['text'][:300]!r}")
    if not found:
        print("(no chunks on gold pages: page excluded from index, or label wrong)")