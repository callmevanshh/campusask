import json
from pathlib import Path

from app.retrieval import search


def best(q):
    return max((c["kw"] for c in search(q, k=4, mode="keyword")), default=0.0)


for name, path in (("dev", "eval/questions.jsonl"), ("test", "eval/questions_test.jsonl"), ("messy", "eval/questions_messy.jsonl"), ("short", "eval/questions_short.jsonl")):
    qs = [json.loads(l) for l in Path(path).open(encoding="utf-8") if l.strip()]
    a = [best(q["q"]) for q in qs if q["answerable"]]
    u = [best(q["q"]) for q in qs if not q["answerable"]]
    print(f"\n{name}: threshold | answerable kept | unanswerable refused")
    for t in [x / 2 for x in range(2, 17)]:
        print(f"  {t:4.1f} | {sum(s >= t for s in a)/len(a):.0%} | {sum(s < t for s in u)/len(u):.0%}")