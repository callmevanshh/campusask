import json
import sys
import time
from pathlib import Path

from app.pipeline import REFUSAL, answer

path = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/answers_gold.jsonl")
rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
counts = {"PASS": 0, "FAIL": 0, "UNAVAILABLE": 0}
out = ["# Answer-level check (substring rules: a PASS is not proof, read every FAIL)\n"]
for r in rows:
    res = answer(r["q"], [], "")
    a = res["answer"]
    low, why = a.lower(), []
    if a.startswith("The AI summary is unavailable"):
        status = "UNAVAILABLE"
    elif r.get("refuse"):
        status = "PASS" if a.strip().startswith(REFUSAL) else "FAIL"
        if status == "FAIL":
            why.append("should have refused")
    else:
        if a.strip().startswith(REFUSAL):
            why.append("refused")
        for group in r.get("all", []):
            if not any(s.lower() in low for s in group):
                why.append(f"missing one of {group}")
        for s in r.get("none", []):
            if s.lower() in low:
                why.append(f"contains {s!r}")
        if not res["sources"]:
            why.append("no sources")
        status = "FAIL" if why else "PASS"
    counts[status] += 1
    print(f"{status:11} | {r['q']}" + (f"  !! {'; '.join(why)}" if why else ""))
    out.append(f"## {r['q']}\n**{status}** {why or ''} (checked against: {r.get('src', '-')})\n\n{a}\n")
    time.sleep(6)
done = counts["PASS"] + counts["FAIL"]
print(f"\n{counts['PASS']} of {done} passed ({counts['UNAVAILABLE']} unavailable, not counted)")
Path("eval/answers_gold_out.md").write_text("\n".join(out), encoding="utf-8")