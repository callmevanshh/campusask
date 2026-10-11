import csv
import re

import pymupdf

MARK = re.compile(r"release\s*[–\-—]\s*version|version\s*\d+\s*\([a-z]+\s*\d{4}\)|revision history|version history", re.I)
for row in csv.DictReader(open("data/sources.csv", encoding="utf-8")):
    f = row["file"]
    if not f.lower().endswith(".pdf"):
        continue
    doc = pymupdf.open(f"data/raw/{f}")
    for i, p in enumerate(doc, 1):
        t = " ".join(p.get_text().split())
        m = MARK.search(t)
        if m:
            print(f"\n{f} page {i}/{len(doc)}  (exclude_pages now: {row.get('exclude_pages') or '-'})")
            print("  BEFORE the marker:", t[max(0, m.start() - 220):m.start()])
            print("  AT the marker:    ", t[m.start():m.start() + 160])