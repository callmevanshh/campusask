import csv
import json
import re
from pathlib import Path

import pymupdf

RAW = Path("data/raw")
OUT = Path("data/processed/chunks.jsonl")
REGISTRY = Path("data/sources.csv")
CHUNK_SIZE = 800
OVERLAP = 150

LETTERHEAD = re.compile(r"INDRAPRASTHA INSTITUTE of.*?www\.iiitd\.ac\.in", re.S)
HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\s+([A-Z][A-Za-z0-9 ,&/()'\-]{3,90})$")
MD_HEADING = re.compile(r"^#{1,3}\s+(.{3,90})$")  # "# Grading scheme" in .txt files


def clean(text):
    text = LETTERHEAD.sub("", text)
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text, size=CHUNK_SIZE, overlap=OVERLAP):
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = text.rfind(" ", start + size // 2, end)
            if cut != -1:
                end = cut
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def last_heading(chunk, current):
    for line in chunk.split("\n"):
        line = line.strip()
        m = HEADING.match(line)
        if m:
            title = re.sub(r"\s*\([^)]*$", "", m.group(2)).strip()
            current = f"{m.group(1)} {title}"
            continue
        m = MD_HEADING.match(line)
        if m:
            current = m.group(1).strip()
    return current


def parse_pages(spec):
    pages = set()
    for part in (spec or "").split(";"):
        part = part.strip()
        if part:
            a, _, b = part.partition("-")
            pages.update(range(int(a), int(b or a) + 1))
    return pages


def iter_pages(path, skip):
    """PDFs give one item per page. .txt/.md files (web pages) give one item."""
    if path.suffix.lower() in (".txt", ".md"):
        yield 1, clean(path.read_text(encoding="utf-8")), "web"
        return
    doc = pymupdf.open(path)
    for page_num, page in enumerate(doc, start=1):
        if page_num in skip:
            continue
        yield page_num, clean(page.get_text()), "pdf"
    doc.close()


def main():
    rows = list(csv.DictReader(REGISTRY.open(encoding="utf-8")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with OUT.open("w", encoding="utf-8") as f:
        for row in rows:
            path = RAW / row["file"]
            if not path.exists():
                print(f"MISSING: {path} (listed in sources.csv but not in data/raw)")
                continue
            skip = parse_pages(row.get("exclude_pages"))
            section, n, pages, empty = "", 0, 0, 0
            for page_num, text, kind in iter_pages(path, skip):
                pages += 1
                if len(text) < 30:
                    empty += 1
                    continue
                for i, c in enumerate(chunk_text(text)):
                    section = last_heading(c, section)
                    rec = {
                        "id": f"{path.stem}-p{page_num}-c{i}",
                        "source": row["file"],
                        "title": row["title"],
                        "version": row["version"],
                        "url": row["url"],
                        "kind": kind,
                        "section": section,
                        "page": page_num,
                        "text": c,
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n += 1
            print(f"{row['file']}: {pages} pages, {n} chunks, {empty} empty/scanned pages skipped")
            total += n
    print(f"\nTotal chunks: {total}")


if __name__ == "__main__":
    main()