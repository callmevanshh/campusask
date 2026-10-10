import base64
import csv
import os
import re
import sys
import time
from pathlib import Path

import httpx
import pymupdf
from dotenv import load_dotenv

load_dotenv()
RAW = Path("data/raw")
OUT = Path("data/tables")
REGISTRY = Path("data/sources.csv")
BRANCHES = {"cse", "csai", "csam", "csd", "csss", "csb", "ece", "eve", "csecon"}
MAX_GROUP = 3

PROMPT = (
    "You are transcribing pages of an official university regulations PDF into Markdown. "
    "Transcribe all text exactly as written. Do not summarize, paraphrase, translate or add anything. "
    "Ignore the letterhead (institute name, address, logo) and page numbers. "
    "Keep headings as lines starting with '#'. "
    "Reproduce every table as a Markdown table with a header row and a separator row. "
    "The caption of each table (for example 'For students of 2024 batch and onwards') must appear as a plain line "
    "directly above that table. "
    "If a table continues across the provided page images (a row or a cell is split at the page break), "
    "merge it into ONE complete table. "
    "Never invent course names. If something is unreadable write [unclear]. Output only the Markdown."
)


def candidates(doc):
    cand = set()
    for i, page in enumerate(doc):
        if len(re.findall(r"Semester\s*\d", page.get_text(), re.I)) >= 3:
            cand.add(i)
        elif (i - 1) in cand and page.find_tables().tables:
            cand.add(i)
    return sorted(cand)


def groups(pages):
    out, cur = [], []
    for p in pages:
        if cur and (p != cur[-1] + 1 or len(cur) >= MAX_GROUP):
            out.append(cur)
            cur = []
        cur.append(p)
    if cur:
        out.append(cur)
    return out


def strip_fences(t):
    t = t.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*\n", "", t)
    return re.sub(r"\n```\s*$", "", t).strip()


def transcribe(doc, idxs):
    key, model = os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL")
    parts = [{"text": PROMPT}]
    for i in idxs:
        png = doc[i].get_pixmap(dpi=150).tobytes("png")
        parts.append({"text": f"Page {i + 1}:"})
        parts.append({"inline_data": {"mime_type": "image/png", "data": base64.b64encode(png).decode()}})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"contents": [{"parts": parts}], "generationConfig": {"temperature": 0}}
    for attempt in range(4):
        r = httpx.post(url, headers={"x-goog-api-key": key}, json=payload, timeout=180)
        if r.status_code in (429, 503) and attempt < 3:
            time.sleep(20 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    return strip_fences("".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"]))


def main():
    run = "--run" in sys.argv
    only = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    OUT.mkdir(parents=True, exist_ok=True)
    todo = []
    for row in csv.DictReader(REGISTRY.open(encoding="utf-8")):
        f = row["file"]
        if not f.lower().endswith(".pdf") or f.split("-")[0].lower() not in BRANCHES:
            continue
        if only and f != only:
            continue
        doc = pymupdf.open(RAW / f)
        for g in groups(candidates(doc)):
            if not (OUT / f"{Path(f).stem}-p{g[0] + 1}.md").exists():
                todo.append((f, g))
        doc.close()
    for f, g in todo:
        print(f"{f}: pages {g[0] + 1}-{g[-1] + 1}")
    print(f"\n{len(todo)} group(s) to transcribe (1 Gemini call each).")
    if not run:
        print("Dry run. Add --run to transcribe.")
        return
    for f, g in todo:
        doc = pymupdf.open(RAW / f)
        md = transcribe(doc, g)
        doc.close()
        if "\n|" not in "\n" + md:
            print(f"SKIPPED {f} pages {g[0] + 1}-{g[-1] + 1}: no table in the transcription")
            continue
        stem = Path(f).stem
        (OUT / f"{stem}-p{g[0] + 1}.md").write_text(md, encoding="utf-8")
        for i in g[1:]:
            (OUT / f"{stem}-p{i + 1}.md").write_text(f"<!-- merged into page {g[0] + 1} -->", encoding="utf-8")
        print(f"saved {stem}-p{g[0] + 1}.md")
        time.sleep(6)


if __name__ == "__main__":
    main()