import json
from pathlib import Path

from app.retrieval import search

DEFAULT_SRC = "UG-Regulations-2025-Oct.pdf"
qs = [json.loads(l) for l in Path("eval/questions.jsonl").open(encoding="utf-8") if l.strip()]
ans = [q for q in qs if q["answerable"]]
unans = [q for q in qs if not q["answerable"]]

out = [f"{len(ans)} answerable, {len(unans)} unanswerable questions", ""]
out.append(f"{'mode':10} {'hit@1':>7} {'hit@3':>7}")

misses = []
for mode in ("semantic", "keyword", "hybrid"):
    h1 = h3 = 0
    for q in ans:
        gold = {(q.get("source", DEFAULT_SRC), p) for p in q["pages"]}
        res = search(q["q"], k=3, mode=mode)
        got = [(c["source"], c["page"]) for c in res]
        h1 += bool(got) and got[0] in gold
        ok3 = any(g in gold for g in got)
        h3 += ok3
        if mode == "hybrid" and not ok3:
            misses.append((q["q"], q["pages"], [p for _, p in got]))
    out.append(f"{mode:10} {h1/len(ans):7.0%} {h3/len(ans):7.0%}")

out += ["", "Hybrid misses (question | expected pages | got pages):"]
out += [f"  {m[0]} | {m[1]} | {m[2]}" for m in misses] or ["  none"]

# refusal threshold sweep (same gate as ask.py: max semantic score over top 4 hybrid chunks)
def max_sem(q):
    return max((c["sem"] for c in search(q["q"], k=4)), default=0.0)

a_scores = [max_sem(q) for q in ans]
u_scores = [max_sem(q) for q in unans]
out += ["", "Threshold sweep:  thr | answerable kept | unanswerable refused"]
for t in [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45]:
    kept = sum(s >= t for s in a_scores) / len(a_scores)
    refused = sum(s < t for s in u_scores) / max(len(u_scores), 1)
    out.append(f"  {t:.2f} | {kept:.0%} | {refused:.0%}")

text = "\n".join(out)
print(text)
Path("eval/results.md").write_text(text, encoding="utf-8")