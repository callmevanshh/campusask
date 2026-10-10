import csv
import json
import re
from pathlib import Path

import pymupdf

RAW = Path("data/raw")
TABLE_DIR = Path("data/tables")
OUT = Path("data/processed/chunks.jsonl")
REGISTRY = Path("data/sources.csv")
CHUNK_SIZE = 800
OVERLAP = 150
TABLE_LIMIT = 2500
TABLE_HINT = "semester-wise course structure core courses curriculum program structure"

LETTERHEAD = re.compile(r"INDRAPRASTHA INSTITUTE of.*?www\.iiitd\.ac\.in", re.S)
HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\s+([A-Z][A-Za-z0-9 ,&/()'\-]{3,90})$")
MD_HEADING = re.compile(r"^#{1,3}\s+(.{3,90})$")
BATCH = re.compile(r"batch", re.I)


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


def last_heading(chunk, current, kind="pdf"):
    for line in chunk.split("\n"):
        line = line.strip()
        m = HEADING.match(line)
        if m:
            title = re.sub(r"\s*\([^)]*$", "", m.group(2)).strip()
            current = f"{m.group(1)} {title}"
            continue
        m = MD_HEADING.match(line)
        if m:
            text = m.group(1).strip()
            # In PDFs a leading '#' is usually a footnote marker, so only accept '#' lines that
            # start with a section number there; web .txt files accept any '#' heading.
            if kind == "web" or re.match(r"\d", text):
                current = text
    return current


def parse_pages(spec):
    pages = set()
    for part in (spec or "").split(";"):
        part = part.strip()
        if part:
            a, _, b = part.partition("-")
            pages.update(range(int(a), int(b or a) + 1))
    return pages


def page_tables(page):
    """Fallback: tables as Markdown via PyMuPDF. Often garbled for merged cells."""
    try:
        found = page.find_tables()
    except Exception:
        return []
    out = []
    for t in found.tables:
        try:
            md = t.to_markdown()
        except Exception:
            continue
        md = md.replace("<br>", " ").strip()
        if len(md.split("\n")) >= 3 and len(md) > 80:
            out.append(md)
    return out


def curated(stem, page_num):
    p = TABLE_DIR / f"{stem}-p{page_num}.md"
    return p.read_text(encoding="utf-8") if p.exists() else None


def parse_curated(md):
    """Split Markdown into prose and tables. Each table gets a caption made of the nearest
    'batch' line (within the last 5 text lines) and the line directly above it."""
    prose, tables, cur, recent, caption = [], [], [], [], ""
    for ln in md.split("\n") + [""]:
        s = ln.strip()
        if s.startswith("|"):
            if not cur:
                batch_lines = [r for r in recent if BATCH.search(r)]
                keep = ([batch_lines[-1]] if batch_lines else []) + ([recent[-1]] if recent else [])
                caption = " — ".join(dict.fromkeys(keep))
            cur.append(s)
            continue
        if cur:
            block = "\n".join(cur)
            tables.append((caption + "\n\n" + block) if caption else block)
            cur = []
        prose.append(ln)
        if s:
            recent = (recent + [re.sub(r"^[#*\s]+|[*\s]+$", "", s)[:150]])[-5:]
    return clean("\n".join(prose)), tables


def batch_start(md):
    """Start year of the batch named in a table's caption, e.g. 'For students 2024 batch and onwards' -> 2024."""
    head = md.split("\n\n", 1)[0]
    if head.lstrip().startswith("|"):
        return None
    for seg in head.split(" — "):
        if BATCH.search(seg):
            m = re.search(r"(?:19|20)\d\d", seg)
            if m:
                return int(m.group(0))
    return None


def split_table(md, limit=TABLE_LIMIT):
    if len(md) <= limit:
        return [md]
    lines = md.split("\n")
    start = next((i for i, l in enumerate(lines) if l.startswith("|")), 0)
    head, body = lines[:start + 2], lines[start + 2:]
    pieces, cur, size = [], [], 0
    for ln in body:
        if size + len(ln) > limit and cur:
            pieces.append("\n".join(head + cur))
            cur, size = [], 0
        cur.append(ln)
        size += len(ln)
    if cur:
        pieces.append("\n".join(head + cur))
    return pieces


def iter_pages(path, skip):
    if path.suffix.lower() in (".txt", ".md"):
        yield 1, clean(path.read_text(encoding="utf-8")), "web", []
        return
    doc = pymupdf.open(path)
    for page_num, page in enumerate(doc, start=1):
        if page_num in skip:
            continue
        cur = curated(path.stem, page_num)
        if cur is not None:
            if cur.lstrip().startswith("<!--"):
                continue  # merged into an earlier page's transcription
            text, tables = parse_curated(cur)
            yield page_num, text, "pdf", tables
        else:
            yield page_num, clean(page.get_text()), "pdf", page_tables(page)
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
            section, pages, empty, ntables, recs = "", 0, 0, 0, []
            for page_num, text, kind, tables in iter_pages(path, skip):
                pages += 1
                if len(text) < 30 and not tables:
                    empty += 1
                    continue
                base = {"source": row["file"], "title": row["title"], "version": row["version"],
                        "url": row["url"], "kind": kind, "page": page_num}
                for i, c in enumerate(chunk_text(text) if len(text) >= 30 else []):
                    section = last_heading(c, section, kind)
                    recs.append({**base, "id": f"{path.stem}-p{page_num}-c{i}", "section": section, "text": c})
                for j, md in enumerate(tables):
                    ntables += 1
                    year = batch_start(md)
                    extra = TABLE_HINT if re.search(r"semester\s*\d", md, re.I) else ""
                    for k, piece in enumerate(split_table(md)):
                        rec = {**base, "id": f"{path.stem}-p{page_num}-t{j}-{k}", "section": section,
                               "table": True, "text": piece}
                        if extra:
                            rec["index_extra"] = extra
                        if year:
                            rec["batch_year"] = year
                        recs.append(rec)
            years = [r["batch_year"] for r in recs if r.get("batch_year")]
            note = ""
            if years:
                top = max(years)
                for r in recs:
                    if r.get("batch_year") == top:
                        r["newest"] = True
                note = f", newest batch table: {top}"
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            print(f"{row['file']}: {pages} pages, {len(recs)} chunks ({ntables} tables), "
                  f"{empty} empty/scanned pages skipped{note}")
            total += len(recs)
    print(f"\nTotal chunks: {total}")


if __name__ == "__main__":
    main()