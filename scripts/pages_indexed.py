import json
import re
from collections import defaultdict

MARK = re.compile(r"release\s*[–\-—]\s*version|version\s*\d+\s*\([a-z]+\s*\d{4}\)|revision history|"
                  r"version history|has been updated|has been made optional|courses added in", re.I)
rows = [json.loads(l) for l in open("data/processed/chunks_kept.jsonl", encoding="utf-8") if l.strip()]
pages, bad = defaultdict(set), defaultdict(set)
for r in rows:
    pages[r["source"]].add(r["page"])
    if MARK.search(r["text"]):
        bad[r["source"]].add(r["page"])
for s in sorted(pages):
    print(f"{s}: indexed pages {sorted(pages[s])} | history-looking chunks on pages {sorted(bad[s]) or '-'}")