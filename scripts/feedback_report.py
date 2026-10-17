import json
import sys
from collections import Counter
from pathlib import Path

src = Path(sys.argv[1] if len(sys.argv) > 1 else "data/feedback.jsonl")
rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
c = Counter(r["verdict"] for r in rows)
rated = c["up"] + c["down"]
print(f"{len(rows)} entries: {c['up']} accurate, {c['down']} not accurate, {c['missed']} 'should have been found'")
if rated:
    print(f"accurate among rated answers: {c['up'] / rated:.0%} ({c['up']}/{rated})")
cands = []
for r in rows:
    if r["verdict"] in ("down", "missed"):
        print(f"\n[{r['verdict']}] {r['question']}\n    note: {r.get('note') or '-'}")
        cands.append({"q": r["question"], "pages": [], "answerable": None, "feedback": r["verdict"], "note": r.get("note", "")})
if cands:
    out = Path("eval/questions_real_candidates.jsonl")
    out.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in cands) + "\n", encoding="utf-8")
    print(f"\nwrote {len(cands)} candidate question(s) to {out}. Fill in pages and answerable by hand, "
          "then move them into eval/questions_real.jsonl.")