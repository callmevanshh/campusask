import csv
import re
import subprocess
from pathlib import Path

import pymupdf

RAW, REG, QUEUE = Path("data/raw"), Path("data/sources.csv"), Path("data/queue.csv")
BRANCHES = {"cse", "csai", "csam", "csd", "csss", "csb", "ece", "eve", "csecon"}
MARK = re.compile(r"release\s*[–\-—]\s*version|version\s*\d+\s*\([a-z]+\s*\d{4}\)|revision history|"
                  r"version history|amendment history", re.I)

have = {r["file"] for r in csv.DictReader(REG.open(encoding="utf-8"))}
added = []
for r in csv.DictReader(QUEUE.open(encoding="utf-8")):
    f, url = r["file"].strip(), r["url"].strip().replace(" ", "%20")
    if not f or f in have:
        print(f"skip   {f}: already in sources.csv")
        continue
    if " " in f or f.split("-")[0].lower() in BRANCHES:
        print(f"RENAME {f}: no spaces, and do not start the name with a program code")
        continue
    dest = RAW / f
    if not dest.exists():
        cmd = ["powershell", "-NoProfile", "-Command",
               f"Invoke-WebRequest -Uri '{url}' -OutFile '{dest}' -UserAgent 'Mozilla/5.0'"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0 or not dest.exists():
            print(f"FAILED {f}: download did not work ({res.stderr.strip()[:120]})")
            continue
    if not dest.read_bytes()[:5].startswith(b"%PDF"):
        dest.unlink()
        print(f"NOT A PDF {f}: probably a web page or Word file. Copy its text into a .txt file instead")
        continue
    try:
        doc = pymupdf.open(dest)
        chars = sum(len(p.get_text()) for p in doc)
    except Exception as e:
        dest.unlink()
        print(f"UNREADABLE {f}: {e!r}")
        continue
    if chars < 300:
        print(f"SCANNED {f}: {len(doc)} pages but almost no text; needs OCR, skipped (file kept)")
        continue
    flagged = [i for i, p in enumerate(doc, 1) if MARK.search(p.get_text())]
    added.append([f, r["title"].strip(), url, r["version"].strip() or "unknown", ""])
    print(f"OK     {f}: {len(doc)} pages, {chars} chars, history-looking pages: {flagged or 'none'}")

if added:
    text = REG.read_text(encoding="utf-8")
    with REG.open("a", encoding="utf-8", newline="") as fh:
        if not text.endswith("\n"):
            fh.write("\n")
        csv.writer(fh, lineterminator="\n").writerows(added)
    print(f"\nregistered {len(added)} document(s) in data/sources.csv")