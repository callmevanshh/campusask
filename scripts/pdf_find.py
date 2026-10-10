import re
import sys

import pymupdf

f, pat = sys.argv[1], sys.argv[2]
for i, p in enumerate(pymupdf.open(f"data/raw/{f}"), 1):
    n = len(re.findall(pat, p.get_text(), re.I))
    if n:
        print(f"page {i}: {n} match(es)")