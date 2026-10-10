import json
from pathlib import Path

CONTAINS = {
    "total credits do I need to graduate": ["156"],
    "online course credits": ["no more than 8"],
    "standard full-semester course": ["of 4 credits", "4-credit course"],
    "Independent Study course": ["independent study"],
    "maximum time allowed to finish": ["maximum duration within which"],
}
path = Path("eval/questions.jsonl")
lines = path.read_text(encoding="utf-8").splitlines()
done = 0
for i, line in enumerate(lines):
    q = json.loads(line)
    for needle, phrases in CONTAINS.items():
        if needle in q["q"]:
            q["contains"] = phrases
            lines[i] = json.dumps(q, ensure_ascii=False)
            done += 1
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("updated", done)