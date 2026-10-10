import json
from pathlib import Path

from app.retrieval import search

DEFAULT_SRC = "UG-Regulations-2025-Oct.pdf"
SETS = ["eval/questions.jsonl", "eval/questions_test.jsonl", "eval/questions_messy.jsonl",
        "eval/questions_short.jsonl", "eval/questions_branch.jsonl"]


def norm(t):
    return " ".join(t.lower().split())


def is_hit(q, c):
    gold = {(q.get("source", DEFAULT_SRC), p) for p in q["pages"]}
    if (c["source"], c["page"]) in gold:
        return True
    return any(norm(n) in norm(c["text"]) for n in q.get("contains", []))


print(f"{'set':8} {'n':>3} {'hit@1':>6} {'hit@3':>6}   (keyword search, as deployed)")
for path in SETS:
    if not Path(path).exists():
        continue
    qs = [json.loads(l) for l in Path(path).open(encoding="utf-8") if l.strip()]
    ans = [q for q in qs if q["answerable"]]
    h1 = h3 = 0
    misses = []
    for q in ans:
        res = search(q["q"], k=3, mode="keyword", branch=q.get("branch"))
        h1 += bool(res) and is_hit(q, res[0])
        ok = any(is_hit(q, c) for c in res)
        h3 += ok
        if not ok:
            got = [f"{c['source'].split('-')[0]}:p{c['page']}" for c in res]
            misses.append(f"      MISS: {q['q']!r} want {q['source'] if 'source' in q else 'UG'}:{q['pages']} got {got}")
    stem = Path(path).stem
    name = "dev" if stem == "questions" else stem.replace("questions_", "")
    print(f"{name:8} {len(ans):3d} {h1/len(ans):6.0%} {h3/len(ans):6.0%}")
    for m in misses:
        print(m)