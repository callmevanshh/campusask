import os
import re
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

SYSTEM = (
    "You are CampusAsk, an assistant for IIIT Delhi students. Answer using ONLY the numbered sources below. "
    "Students write informally, with typos, abbreviations and sometimes Hinglish, so match the meaning of the question to the sources, not the exact words. "
    "Reply in the language the student used (English, or Hinglish in Roman script). "
    "The sources may come from different documents (UG regulations, ordinances, and branch-specific regulations such as CSE or CSB). "
    "If the answer differs between branches or batches, say which branch or batch each rule applies to. "
    "If it depends on the student's branch or batch and none is given, give the general UG rule and say the branch regulations may differ. "
    "A course table's batch is stated only in the caption line just above it (for example 'For students 2024 batch and onwards'). "
    "Never assign a batch to a table unless its caption says so; if there is no caption, say the batch is not stated. "
    "Never mix courses from different batches' tables in one list. "
    "If the student does not mention a batch and several batches are available, answer with the newest batch (the latest year) and add one line saying older batches follow different tables. "
    "Match the format to the question. For a simple factual question, answer in 1 to 3 sentences. "
    "For a rule with several conditions, use short bullet points. "
    "For questions asking for requirements, criteria or rules, include every relevant item found in ALL the sources, not only the first one. "
    "For comparisons, semester-wise lists, or anything naturally tabular, use a Markdown table (header row, separator row, then rows). "
    "In a table cell that holds several items (for example several courses), separate them with <br> so each item is on its own line; never run course names together in one line. "
    "Bold the key number or term. Do not add background the student did not ask for. "
    "Cite sources like [1] after each claim, one number per bracket; for a table put the citation after the table. "
    "If the sources only partly answer the question, say what they cover and what is missing. "
    "When useful, name the document and its version (for example 'According to the UG Regulations (Oct 2025)...'). "
    "If the question is not about IIIT Delhi academic rules, or the sources contain nothing relevant, reply exactly: 'I could not find this in the documents.' "
    "Do not chat, joke or answer general-knowledge questions. "
    "Never use outside knowledge and never invent numbers, courses or rules. "
    "If a table in the sources looks garbled or incomplete, say so and point the student to the official PDF instead of guessing."
)

def _history_text(history):
    if not history:
        return ""
    lines = []
    for t in history[-4:]:
        who = "Student" if t["role"] == "user" else "CampusAsk"
        text = re.sub(r"\[[\d,\s]+\]", "", t["text"])[:400]
        lines.append(f"{who}: {text}")
    return ("CONVERSATION SO FAR (only to understand what the new question refers to; "
            "facts must come from SOURCES):\n" + "\n".join(lines) + "\n\n")


def generate(question, chunks, history=None, branch=""):
    key, model = os.getenv("GEMINI_API_KEY"), os.getenv("GEMINI_MODEL")
    if not key or not model:
        raise RuntimeError("Set GEMINI_API_KEY and GEMINI_MODEL in .env")
    context = "\n\n".join(
        f"[{i+1}] ({c.get('title', c['source'])}, {c.get('version') or 'n/a'}, "
        f"section: {c.get('section') or 'n/a'}, page {c['page']})\n{c['text']}"
        for i, c in enumerate(chunks)
    )
    who = f"The student says their program/branch is {branch.upper()}.\n\n" if branch else ""
    prompt = f"{SYSTEM}\n\n{who}{_history_text(history)}SOURCES:\n{context}\n\nQUESTION: {question}"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1}}
    for attempt in range(4):
        r = httpx.post(url, headers={"x-goog-api-key": key}, json=payload, timeout=60)
        if r.status_code in (429, 503) and attempt < 3:
            time.sleep(15 * (attempt + 1))
            continue
        r.raise_for_status()
        break
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)