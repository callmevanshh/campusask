import csv
import re

import pymupdf

MARK = re.compile(r"release\s*[–\-—]\s*version|version\s*\d+\s*\([a-z]+\s*\d{4}\)|revision history|version history", re.I)

for row in csv.DictReader(open("data/sources.csv", encoding="utf-8")):
    f = row["file"]
    if not f.lower().endswith(".pdf"):
        continue
    doc = pymupdf.open(f"data/raw/{f}")
    hits = [i for i, p in enumerate(doc, 1) if MARK.search(p.get_text())]
    now = row.get("exclude_pages") or "-"
    if hits:
        first = doc[hits[0] - 1].get_text().strip().replace("\n", " ")[:140]
        print(f"{f}: {len(doc)} pages | history lines on pages {hits} | exclude_pages now: {now}")
        print(f"    page {hits[0]} starts with: {first}")
    else:
        print(f"{f}: {len(doc)} pages | no history markers found | exclude_pages now: {now}")