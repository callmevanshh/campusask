import json
import sys
from pathlib import Path

from app.retrieval import search

DEFAULT_SRC = "UG-Regulations-2025-Oct.pdf"
path = sys.argv[1] if len(sys.argv) > 1 else "eval/questions.jsonl"
qs = [json.loads(l) for l in Path(path).open(encoding="utf-8") if l.strip()]
ans = [q for q in qs if q["answerable"]]
unans = [q for q in qs if not q["answerable"]]


def norm(t):
    return " ".join(t.lower().split())


def is_hit(q, c):
    """A chunk counts if it is on a gold page, or contains a phrase that proves it answers the question."""
    gold = {(q.get("source", DEFAULT_SRC), p) for p in q["pages"]}
    if (c["source"], c["page"]) in gold:
        return True
    text = norm(c["text"])
    return any(norm(n) in text for n in q.get("contains", []))


out = [f"{len(ans)} answerable, {len(unans)} unanswerable questions", ""]
out.append(f"{'mode':10} {'hit@1':>7} {'hit@3':>7}")

misses = []
for mode in ("semantic", "keyword", "hybrid"):
    h1 = h3 = 0
    for q in ans:
        res = search(q["q"], k=3, mode=mode)
        h1 += bool(res) and is_hit(q, res[0])
        ok3 = any(is_hit(q, c) for c in res)
        h3 += ok3
        if mode == "keyword" and not ok3:
            misses.append((q["q"], q["pages"], [f"{c['source'].split('-')[0]}:p{c['page']}" for c in res]))
    out.append(f"{mode:10} {h1/len(ans):7.0%} {h3/len(ans):7.0%}")

out += ["", "Keyword misses (question | expected pages | got):"]
out += [f"  {m[0]} | {m[1]} | {m[2]}" for m in misses] or ["  none"]

path_out = Path("eval/results.md")
text = "\n".join(out)
print(text)
path_out.write_text(text, encoding="utf-8")