import json
import sys
from pathlib import Path

from app.retrieval import search

DEFAULT_SRC = "UG-Regulations-2025-Oct.pdf"
SETS = ["eval/questions.jsonl", "eval/questions_test.jsonl", "eval/questions_messy.jsonl",
        "eval/questions_short.jsonl", "eval/questions_branch.jsonl"]
LABELS = {"dev": "Dev", "test": "Test (written after the dev set)", "messy": "Informal wording and typos",
          "short": "Very short questions", "branch": "Program-specific"}
VERBOSE = "--verbose" in sys.argv
MD = "--md" in sys.argv
MIN3 = next((float(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--min-hit3=")), 0.0)


def norm(t):
    return " ".join(t.lower().split())


def is_hit(q, c):
    gold = {(q.get("source", DEFAULT_SRC), p) for p in q["pages"]}
    if (c["source"], c["page"]) in gold:
        return True
    return any(norm(n) in norm(c["text"]) for n in q.get("contains", []))


print(f"{'set':8} {'n':>3} {'hit@1':>6} {'hit@3':>6} {'hit@6':>6}   (keyword search as deployed; the live answer sees about 6 to 8 chunks)")
below, rows = [], []
for path in SETS:
    if not Path(path).exists():
        continue
    qs = [json.loads(l) for l in Path(path).open(encoding="utf-8") if l.strip()]
    ans = [q for q in qs if q["answerable"]]
    h1 = h3 = h6 = 0
    notes = []
    for q in ans:
        res = search(q["q"], k=6, mode="keyword", branch=q.get("branch"), expand=False)
        hits = [is_hit(q, c) for c in res]
        h1 += bool(hits) and hits[0]
        h3 += any(hits[:3])
        h6 += any(hits)
        got = [f"{c['source'].split('-')[0]}:p{c['page']}" for c in res[:3]]
        want = f"{q.get('source', 'UG').split('-')[0]}:{q['pages']}"
        if not any(hits[:3]):
            notes.append(f"      MISS@3{'' if any(hits) else ' (and @6)'}: {q['q']!r} want {want} got {got}")
        elif VERBOSE and not (hits and hits[0]):
            notes.append(f"      not top-1: {q['q']!r} want {want} got {got}")
    stem = Path(path).stem
    name = "dev" if stem == "questions" else stem.replace("questions_", "")
    n = len(ans)
    print(f"{name:8} {n:3d} {h1/n:6.0%} {h3/n:6.0%} {h6/n:6.0%}")
    rows.append(f"| {LABELS.get(name, name)} | {n} | {h1/n:.0%} | {h3/n:.0%} | {h6/n:.0%} |")
    for m in notes:
        print(m)
    if h3 / n < MIN3:
        below.append(f"{name} ({h3 / n:.0%})")
if MD:
    print("\n| Set | Answerable questions | hit@1 | hit@3 | hit@6 |\n|---|---|---|---|---|\n" + "\n".join(rows))
if below:
    print(f"\nFAILED: hit@3 is below {MIN3:.0%} in: {', '.join(below)}")
    sys.exit(1)