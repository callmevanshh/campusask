import json
from pathlib import Path

FLIP = {
    "How much is the total tuition fee per semester for BTech?":
        {"pages": [1], "source": "Fee-Schedule-25.26.txt", "contains": ["tuition"]},
    "mess menu today":
        {"pages": [6], "source": "Final-Hostel-Management.pdf", "contains": ["menu"]},
    "What is the mess menu this week?":
        {"pages": [6], "source": "Final-Hostel-Management.pdf", "contains": ["menu"]},
}
n = 0
for f in sorted(Path("eval").glob("questions*.jsonl")):
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        if q["q"] in FLIP and not q["answerable"]:
            q.update(FLIP[q["q"]])
            q["answerable"] = True
            n += 1
        out.append(json.dumps(q, ensure_ascii=False))
    f.write_text("\n".join(out) + "\n", encoding="utf-8")
print("flipped", n, "question(s) to answerable")