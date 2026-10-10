import csv
import sys
from pathlib import Path

import httpx

target = sys.argv[1]
for row in csv.DictReader(open("data/sources.csv", encoding="utf-8")):
    if row["file"] == target:
        r = httpx.get(row["url"], follow_redirects=True, timeout=60,
                      headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            sys.exit("Downloaded file is not a PDF: " + r.headers.get("content-type", ""))
        Path("data/raw", target).write_bytes(r.content)
        print("saved", target, len(r.content), "bytes")
        break
else:
    sys.exit("not found in sources.csv: " + target)