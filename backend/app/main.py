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
    if os.getenv("SEED_SAMPLE_DATA", "false").lower() in {"1", "true", "yes"}:
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


@app.get("/api/workflow/summary", response_model=schemas.WorkflowQueueSummary)
def workflow_summary(db: Session = Depends(get_db)) -> schemas.WorkflowQueueSummary:
    return crud.workflow_queue_summary(db)


@app.get("/api/workflow/queues/{stage}", response_model=schemas.WorkflowQueueResponse)
def workflow_queue(
    stage: schemas.WorkflowStage,
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> schemas.WorkflowQueueResponse:
    return crud.workflow_queue(db=db, stage=stage, limit=limit, offset=offset)


@app.post("/api/workflow/intake", response_model=schemas.ClaimRead)
def create_intake_claim(
    payload: schemas.IntakeClaimCreate,
    db: Session = Depends(get_db),
) -> schemas.ClaimRead:
    return crud.create_intake_claim(db, payload)


@app.post("/api/workflow/fact-check/{claim_id}", response_model=schemas.ClaimRead)
def submit_fact_check(
    claim_id: int,
    payload: schemas.FactCheckSubmission,
    db: Session = Depends(get_db),
) -> schemas.ClaimRead:
    try:
        return crud.submit_fact_check(db, claim_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.post("/api/workflow/editorial/{claim_id}", response_model=schemas.ClaimRead)
def submit_editorial_decision(
    claim_id: int,
    payload: schemas.EditorialDecision,
    db: Session = Depends(get_db),
) -> schemas.ClaimRead:
    try:
        return crud.submit_editorial_decision(db, claim_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.patch("/api/claims/{claim_id}", response_model=schemas.ClaimRead)
def update_claim(
    claim_id: int,
    payload: schemas.ClaimPatchPayload,
    db: Session = Depends(get_db),
) -> schemas.ClaimRead:
    try:
        return crud.update_claim(db, claim_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.put("/api/claims/{claim_id}/sources", response_model=schemas.ClaimRead)
def replace_sources(
    claim_id: int,
    payload: schemas.SourcesReplacePayload,
    db: Session = Depends(get_db),
) -> schemas.ClaimRead:
    try:
        return crud.replace_sources(db, claim_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.post("/api/workflow/reopen/{claim_id}", response_model=schemas.ClaimRead)
def reopen_claim(
    claim_id: int,
    payload: schemas.ReopenPayload,
    db: Session = Depends(get_db),
) -> schemas.ClaimRead:
    try:
        return crud.reopen_claim(db, claim_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@app.delete("/api/claims/{claim_id}", response_model=schemas.DeleteResponse)
def delete_claim(
    claim_id: int,
    db: Session = Depends(get_db),
) -> schemas.DeleteResponse:
    try:
        crud.delete_claim(db, claim_id)
        return schemas.DeleteResponse(id=claim_id, deleted=True, message="Claim deleted")
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


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
