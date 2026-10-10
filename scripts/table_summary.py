import re
from pathlib import Path

for f in sorted(Path("data/tables").glob("*.md")):
    t = f.read_text(encoding="utf-8")
    if t.lstrip().startswith("<!--"):
        continue
    lines = t.split("\n")
    rows = sum(1 for l in lines if l.strip().startswith("|"))
    unclear = t.count("[unclear]")
    caps = [l.strip()[:70] for l in lines if re.search(r"batch|onwards|students of", l, re.I)]
    print(f"{f.name}: {rows} table rows, {unclear} [unclear], captions: {caps}")