from fastapi import FastAPI

app = FastAPI(title="CampusAsk")

@app.get("/health")
def health():
    return {"status": "ok"}