import sys

import pymupdf

path, page_no = sys.argv[1], int(sys.argv[2])
page = pymupdf.open(path)[page_no - 1]
tabs = page.find_tables().tables
print("tables found:", len(tabs))
for i, t in enumerate(tabs):
    print(f"\n--- table {i} ---")
    print(t.to_markdown())