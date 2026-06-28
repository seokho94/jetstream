"""FastAPI app. Run: uvicorn api.main:app --reload  (http://localhost:8000)

Endpoints follow docs/design/api-contract.md (REST + per-view BFF). Reads from
Postgres when DATABASE_URL is reachable (X-Data-Source: db), else seed (: seed).
"""
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware

from . import repo, seed
from .schemas import BoardView, CurrentView, Digest

app = FastAPI(title="Jetstream API", version="0.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Phase 0 dev; tighten in deploy.
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/v1/board", response_model=BoardView)
def get_board(response: Response) -> BoardView:
    board, source = repo.get_board()
    response.headers["X-Data-Source"] = source
    response.headers["ETag"] = board.etag
    response.headers["Cache-Control"] = "public, max-age=60"  # POLL_INTERVAL
    return board


@app.get("/v1/currents")
def list_currents(response: Response) -> dict:
    currents, source = repo.list_currents()
    response.headers["X-Data-Source"] = source
    return {"source": source, "currents": currents}


@app.get("/v1/currents/{current_id}", response_model=CurrentView)
def get_current(current_id: str, response: Response) -> CurrentView:
    cv, source = repo.get_current(current_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="current not found")
    response.headers["X-Data-Source"] = source
    response.headers["ETag"] = cv.etag
    return cv


@app.get("/v1/digests/{issue}", response_model=Digest)
def get_digest(issue: int, response: Response) -> Digest:
    digest, source = repo.get_digest(issue)
    response.headers["X-Data-Source"] = source
    return digest


@app.get("/v1/search")
def get_search(q: str = "") -> dict:
    return {"q": q, "results": seed.search(q)}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "db": repo.db_available()}
