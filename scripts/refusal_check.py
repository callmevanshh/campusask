import json
import time
from pathlib import Path

from app.pipeline import REFUSAL, answer

files = ["eval/questions.jsonl", "eval/questions_test.jsonl",
         "eval/questions_messy.jsonl", "eval/questions_short.jsonl"]
qs = []
for f in files:
    qs += [json.loads(l) for l in Path(f).open(encoding="utf-8") if l.strip()]
unans = sorted({q["q"] for q in qs if not q["answerable"]})

refused = answered = errors = 0
for q in unans:
    a = answer(q)["answer"]
    if a.strip().startswith(REFUSAL):
        refused += 1; tag = "REFUSED "
    elif a.startswith("The AI summary is unavailable"):
        errors += 1; tag = "ERROR   "
    else:
        answered += 1; tag = "ANSWERED"
    print(tag, q)
    if tag == "ANSWERED":
        print("          ->", a[:160].replace("\n", " "))
    time.sleep(5)

print(f"\nrefused {refused}, answered {answered}, api errors {errors}, total {len(unans)}")