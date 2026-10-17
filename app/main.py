import hmac
import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app.pipeline import answer

app = FastAPI(title="CampusAsk")
_hits = defaultdict(deque)
_fb_hits = defaultdict(deque)
FEEDBACK_FILE = Path("data/feedback.jsonl")
ADMIN_KEY = os.getenv("ADMIN_KEY", "")


def too_many(ip: str, limit: int = 8, window: int = 60, store=None) -> bool:
    store = _hits if store is None else store
    now = time.time()
    q = store[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def client_ip(request: Request) -> str:
    return request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=800)


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=300)
    history: list[Turn] = Field(default_factory=list, max_length=14)
    branch: str = Field(default="", max_length=10)


class Feedback(BaseModel):
    verdict: Literal["up", "down", "missed"]
    question: str = Field(max_length=300)
    answer: str = Field(max_length=4000)
    note: str = Field(default="", max_length=500)


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest, request: Request):
    if too_many(client_ip(request)):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a minute.")
    try:
        return answer(req.question.strip(), [t.model_dump() for t in req.history], req.branch)
    except httpx.HTTPError as e:
        body = getattr(getattr(e, "response", None), "text", "")[:500]
        print("LLM ERROR:", repr(e), body)
        raise HTTPException(status_code=503, detail="The answer service is busy or its limit was reached. Try again in a minute.")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
def feedback(fb: Feedback, request: Request):
    """Stored only when the student presses a feedback button. No IP address is kept."""
    if too_many(client_ip(request), limit=20, store=_fb_hits):
        raise HTTPException(status_code=429, detail="Too much feedback. Please wait a minute.")
    rec = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "verdict": fb.verdict,
           "question": fb.question, "answer": fb.answer, "note": fb.note}
    line = json.dumps(rec, ensure_ascii=False)
    print("[feedback]", line)
    try:
        FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with FEEDBACK_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        print("[feedback] could not write the file:", e)
    return {"ok": True}


@app.get("/admin/feedback")
def export_feedback(x_admin_key: str = Header(default="")):
    if not ADMIN_KEY or not hmac.compare_digest(x_admin_key.encode(), ADMIN_KEY.encode()):
        raise HTTPException(status_code=404, detail="Not found")
    return PlainTextResponse(FEEDBACK_FILE.read_text(encoding="utf-8") if FEEDBACK_FILE.exists() else "")


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")