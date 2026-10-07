import time
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.pipeline import answer

app = FastAPI(title="CampusAsk")
_hits = defaultdict(deque)


def too_many(ip: str, limit: int = 8, window: int = 60) -> bool:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=300)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
def ask(req: AskRequest, request: Request):
    ip = request.headers.get("x-forwarded-for", request.client.host).split(",")[0].strip()
    if too_many(ip):
        raise HTTPException(status_code=429, detail="Too many questions. Please wait a minute.")
    try:
        return answer(req.question.strip())
    except httpx.HTTPError as e:
        body = getattr(getattr(e, "response", None), "text", "")[:500]
        print("LLM ERROR:", repr(e), body)
        raise HTTPException(status_code=503, detail="The answer service is busy or its limit was reached. Try again in a minute.")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")