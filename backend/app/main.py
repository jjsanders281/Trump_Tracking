from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, schemas
from .db import Base, engine, get_db
from .seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if os.getenv("SEED_SAMPLE_DATA", "true").lower() in {"1", "true", "yes"}:
        with Session(engine) as db:
            seed_demo_data(db)
    yield


app = FastAPI(title="Trump Tracking MVP", version="0.1.0", lifespan=lifespan)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> schemas.DashboardSummary:
    return crud.dashboard_summary(db)


@app.get("/api/claims/search", response_model=schemas.ClaimSearchResponse)
def search_claims(
    q: Optional[str] = Query(default=None),
    topic: Optional[str] = Query(default=None),
    verdict: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    min_impact: Optional[int] = Query(default=None, ge=1, le=5),
    verified_only: bool = Query(default=True),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.ClaimSearchResponse:
    try:
        filters = schemas.SearchFilters(
            q=q,
            topic=topic,
            verdict=verdict,
            start_date=start_date,
            end_date=end_date,
            min_impact=min_impact,
            verified_only=verified_only,
        )
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return crud.search_claims(db=db, filters=filters, limit=limit, offset=offset)


@app.get("/api/claims/{claim_id}", response_model=schemas.ClaimRead)
def get_claim(claim_id: int, db: Session = Depends(get_db)) -> schemas.ClaimRead:
    claim = crud.get_claim(db, claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@app.post("/api/claims", response_model=schemas.ClaimRead)
def create_claim(payload: schemas.ClaimBundleCreate, db: Session = Depends(get_db)) -> schemas.ClaimRead:
    claim = crud.create_claim_bundle(db, payload)
    return crud.get_claim(db, claim.id)  # type: ignore[return-value]
