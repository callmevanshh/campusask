import json
import time
import sys
from pathlib import Path

from app.pipeline import answer

qs = [json.loads(l) for l in Path("eval/questions_test.jsonl").open(encoding="utf-8") if l.strip()]
only = {int(x) for x in sys.argv[1:]}
out = []
for i, q in enumerate(qs, 1):
    if only and i not in only:
        continue
    try:
        r = answer(q["q"])
        a = r["answer"]
        pages = ", ".join(f"p.{s['page']}" for s in r["sources"]) or "none"
    except Exception as e:
        a, pages = f"ERROR: {e!r}", "none"
    exp = f"answerable (gold pages {q['pages']})" if q["answerable"] else "UNANSWERABLE"
    out.append(f"## {i}. {q['q']}\nExpected: {exp}\n\nAnswer: {a}\n\nCited pages: {pages}\n\nGrade: \n")
    print(i, "done")
    time.sleep(15)

Path("eval/answers_test_rerun.md" if only else "eval/answers_test.md").write_text("\n".join(out), encoding="utf-8")