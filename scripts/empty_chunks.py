import json
import re

n = 0
for line in open("data/processed/chunks_kept.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if not re.search(r"[A-Za-z0-9]", re.sub(r"\bCol\d+\b", "", r["text"])):
        n += 1
        print(r["id"], "|", r["source"], "page", r["page"], "| table:", bool(r.get("table")), "| section:", r.get("section"))
print(f"{n} chunk(s) without any text")