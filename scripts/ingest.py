import json
import re
from pathlib import Path

import fitz  # this is PyMuPDF

RAW = Path("data/raw")
OUT = Path("data/processed/chunks.jsonl")
CHUNK_SIZE = 800
OVERLAP = 150

HEADER = re.compile(r"INDRAPRASTHA INSTITUTE of.*?www\.iiitd\.ac\.in", re.S)

def clean(text: str) -> str:
    text = HEADER.sub("", text)
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # try to cut at a space instead of mid-word
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


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in data/raw/")
        return

    total_chunks = 0
    for pdf in pdfs:
        doc = fitz.open(pdf)
        skipped = 0
        file_chunks = 0
        with OUT.open("a" if pdf != pdfs[0] else "w", encoding="utf-8") as f:
            for page_num, page in enumerate(doc, start=1):
                text = clean(page.get_text())
                if len(text) < 30:
                    skipped += 1  # blank page or scanned image
                    continue
                for i, c in enumerate(chunk_text(text)):
                    rec = {
                        "id": f"{pdf.stem}-p{page_num}-c{i}",
                        "source": pdf.name,
                        "page": page_num,
                        "text": c,
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    file_chunks += 1
        print(f"{pdf.name}: {len(doc)} pages, {file_chunks} chunks, {skipped} pages skipped")
        total_chunks += file_chunks
        doc.close()

    print(f"\nTotal chunks: {total_chunks}")


if __name__ == "__main__":
    main()