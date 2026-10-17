import json
import re
import time
from pathlib import Path

from app.pipeline import REFUSAL, answer

files = ["eval/questions.jsonl", "eval/questions_test.jsonl",
         "eval/questions_messy.jsonl", "eval/questions_short.jsonl"]
SOFT = re.compile(r"does not (?:explicitly )?(?:state|specify|mention|contain|provide)|"
                  r"do not (?:state|specify|mention|contain)|not (?:specified|mentioned|stated|covered)", re.I)
qs = []
for f in files:
    qs += [json.loads(l) for l in Path(f).open(encoding="utf-8") if l.strip()]
unans = sorted({q["q"] for q in qs if not q["answerable"]})

n = {"REFUSED": 0, "SOFT": 0, "ANSWERED": 0, "ERROR": 0}
for q in unans:
    a = answer(q)["answer"]
    if a.strip().startswith(REFUSAL):
        tag = "REFUSED"
    elif a.startswith("The AI summary is unavailable"):
        tag = "ERROR"
    elif SOFT.search(a):
        tag = "SOFT"  # answered by saying the documents do not state it: acceptable
    else:
        tag = "ANSWERED"
    n[tag] += 1
    print(f"{tag:8} {q}")
    if tag in ("SOFT", "ANSWERED"):
        print("          ->", a[:200].replace("\n", " "))
    time.sleep(5)
print(f"\nrefused {n['REFUSED']}, soft {n['SOFT']}, answered {n['ANSWERED']}, errors {n['ERROR']}, total {len(unans)}")