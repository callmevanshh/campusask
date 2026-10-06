import json
from pathlib import Path

# Format: line_number: (needle_text, pages_list, is_answerable)
PATCH = {
    11: ("8th semester internship", [11, 22], True),
    12: ("total credits", [25], True),
    13: ("Honors degree", [26], True),
    14: ("worst grades", [19], True),
    15: ("online course credits", [7], True),
    16: ("Delhi vs Outside Delhi", [3, 4], True),
    17: ("branch transfer", [23, 24], True),
    18: ("medical leaves", [12], True),
    19: ("fail in a core course", [15, 16], True),
    20: ("standard full-semester", [6], True),
    21: ("extra credits", [10, 11], True),
    23: ("TA duty", [7], True),
    24: ("non-credit", [14, 15], True),
    25: ("already got a C", [16], True),
    26: ("mid-sem exam", [13], True),
    27: ("Minor", [26], True),
    28: ("Honors thesis", [], False),
    30: ("two decimal places", [], False),
    31: ("Independent Study", [7], True),
    32: ("summer term", [10], True),
    33: ("academic dishonesty", [28], True),
    34: ("all registered courses", [17], True),
    35: ("audit a course", [14], True),
    36: ("minimum grade needed to pass", [14, 15], True),
    37: ("BTech Project BTP", [], False),
}

path = Path("eval/questions.jsonl")
lines = path.read_text(encoding="utf-8").splitlines()

for n, (needle, pages, is_ans) in PATCH.items():
    q = json.loads(lines[n - 1])
    assert needle in q["q"], f"Line {n} mismatch: {q['q']}"
    q["pages"] = pages
    q["answerable"] = is_ans
    lines[n - 1] = json.dumps(q, ensure_ascii=False)

path.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Successfully patched {len(PATCH)} questions!")