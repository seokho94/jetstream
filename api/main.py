"""FastAPI app. Run: uvicorn api.main:app --reload  (http://localhost:8000)

Endpoints follow docs/design/api-contract.md (REST + per-view BFF). Phase 0
serves seed data; caching/ISR/ETag semantics are stubbed via headers.
"""
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import seed
from .schemas import BoardView, CurrentView, Digest

app = FastAPI(title="Meridian API", version="0.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 0 dev; tighten in deploy.
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/v1/board", response_model=BoardView)
def get_board(response: Response) -> BoardView:
    board = seed.build_board()
    response.headers["ETag"] = board.etag
    response.headers["Cache-Control"] = "public, max-age=60"  # POLL_INTERVAL
    return board


@app.get("/v1/currents/{current_id}", response_model=CurrentView)
def get_current(current_id: str, response: Response) -> CurrentView:
    cv = seed.build_current(current_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="current not found")
    response.headers["ETag"] = cv.etag
    return cv


@app.get("/v1/digests/{issue}", response_model=Digest)
def get_digest(issue: int) -> Digest:
    return seed.build_digest(issue)


@app.get("/v1/search")
def get_search(q: str = "") -> dict:
    return {"q": q, "results": seed.search(q)}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}
