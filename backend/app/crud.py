from __future__ import annotations

from datetime import datetime, time
from typing import Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from . import models, schemas


def _latest_assessment(assessments: list[models.Assessment]) -> Optional[models.Assessment]:
    if not assessments:
        return None
    return sorted(assessments, key=lambda item: (item.verified_at or item.created_at), reverse=True)[0]


def _serialize_claim(claim: models.Claim) -> schemas.ClaimRead:
    latest = _latest_assessment(claim.assessments)
    return schemas.ClaimRead(
        id=claim.id,
        claim_text=claim.claim_text,
        topic=claim.topic,
        claim_kind=claim.claim_kind,
        statement=schemas.StatementRead.model_validate(claim.statement),
        latest_assessment=(
            schemas.AssessmentRead.model_validate(latest) if latest is not None else None
        ),
        sources=[schemas.SourceRead.model_validate(source) for source in claim.sources],
        tags=[schemas.TagRead.model_validate(tag) for tag in claim.tags],
    )


def _get_or_create_tags(db: Session, tag_names: list[str]) -> list[models.Tag]:
    tag_objects: list[models.Tag] = []
    for raw_name in tag_names:
        name = raw_name.strip().lower()
        if not name:
            continue
        existing = db.query(models.Tag).filter(models.Tag.name == name).first()
        if existing:
            tag_objects.append(existing)
            continue
        created = models.Tag(name=name)
        db.add(created)
        db.flush()
        tag_objects.append(created)
    return tag_objects


def create_claim_bundle(db: Session, payload: schemas.ClaimBundleCreate) -> models.Claim:
    statement = models.Statement(
        occurred_at=payload.statement.occurred_at,
        speaker=payload.statement.speaker,
        venue=payload.statement.venue,
        quote=payload.statement.quote,
        context=payload.statement.context,
        primary_source_url=payload.statement.primary_source_url,
        media_url=payload.statement.media_url,
        region=payload.statement.region,
        impact_score=payload.statement.impact_score,
    )
    db.add(statement)
    db.flush()

    claim = models.Claim(
        statement_id=statement.id,
        claim_text=payload.claim.claim_text,
        topic=payload.claim.topic,
        claim_kind=payload.claim.claim_kind,
    )
    claim.tags = _get_or_create_tags(db, payload.claim.tags)
    db.add(claim)
    db.flush()

    for source in payload.sources:
        db.add(
            models.Source(
                claim_id=claim.id,
                publisher=source.publisher,
                url=source.url,
                source_tier=source.source_tier,
                is_primary=source.is_primary,
                archived_url=source.archived_url,
                notes=source.notes,
            )
        )

    if payload.assessment:
        db.add(
            models.Assessment(
                claim_id=claim.id,
                verdict=payload.assessment.verdict,
                rationale=payload.assessment.rationale,
                reviewer_primary=payload.assessment.reviewer_primary,
                reviewer_secondary=payload.assessment.reviewer_secondary,
                source_tier_used=payload.assessment.source_tier_used,
                publish_status=payload.assessment.publish_status,
                verified_at=payload.assessment.verified_at,
            )
        )

    db.commit()

    return (
        db.query(models.Claim)
        .options(
            selectinload(models.Claim.statement),
            selectinload(models.Claim.assessments),
            selectinload(models.Claim.sources),
            selectinload(models.Claim.tags),
        )
        .filter(models.Claim.id == claim.id)
        .one()
    )


def get_claim(db: Session, claim_id: int) -> Optional[schemas.ClaimRead]:
    claim = (
        db.query(models.Claim)
        .options(
            selectinload(models.Claim.statement),
            selectinload(models.Claim.assessments),
            selectinload(models.Claim.sources),
            selectinload(models.Claim.tags),
        )
        .filter(models.Claim.id == claim_id)
        .first()
    )
    if not claim:
        return None
    return _serialize_claim(claim)


def search_claims(
    db: Session,
    filters: schemas.SearchFilters,
    limit: int,
    offset: int,
) -> schemas.ClaimSearchResponse:
    query = (
        db.query(models.Claim)
        .join(models.Statement)
        .options(
            selectinload(models.Claim.statement),
            selectinload(models.Claim.assessments),
            selectinload(models.Claim.sources),
            selectinload(models.Claim.tags),
        )
    )

    if filters.q:
        like = f"%{filters.q.strip()}%"
        query = query.filter(
            or_(
                models.Claim.claim_text.ilike(like),
                models.Statement.quote.ilike(like),
                models.Statement.context.ilike(like),
            )
        )

    if filters.topic:
        query = query.filter(models.Claim.topic == filters.topic)

    if filters.start_date:
        query = query.filter(
            models.Statement.occurred_at >= datetime.combine(filters.start_date, time.min)
        )

    if filters.end_date:
        query = query.filter(models.Statement.occurred_at <= datetime.combine(filters.end_date, time.max))

    if filters.min_impact:
        query = query.filter(models.Statement.impact_score >= filters.min_impact)

    needs_assessment_join = bool(filters.verdict) or filters.verified_only
    if needs_assessment_join:
        query = query.join(models.Assessment)
        if filters.verdict:
            query = query.filter(models.Assessment.verdict == filters.verdict)
        if filters.verified_only:
            query = query.filter(models.Assessment.publish_status == "verified")

    query = query.distinct()

    total = query.count()
    claims = (
        query.order_by(models.Statement.occurred_at.desc(), models.Claim.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [_serialize_claim(claim) for claim in claims]

    return schemas.ClaimSearchResponse(total=total, limit=limit, offset=offset, items=items)


def dashboard_summary(db: Session) -> schemas.DashboardSummary:
    total_claims = db.query(models.Claim).count()
    verified_claims = (
        db.query(func.count(func.distinct(models.Assessment.claim_id)))
        .filter(models.Assessment.publish_status == "verified")
        .scalar()
        or 0
    )
    contradiction_links = db.query(models.Contradiction).count()

    verdict_rows = (
        db.query(models.Assessment.verdict, func.count(models.Assessment.id))
        .filter(models.Assessment.publish_status == "verified")
        .group_by(models.Assessment.verdict)
        .all()
    )

    topic_rows = (
        db.query(models.Claim.topic, func.count(models.Claim.id))
        .group_by(models.Claim.topic)
        .order_by(func.count(models.Claim.id).desc())
        .limit(12)
        .all()
    )

    return schemas.DashboardSummary(
        total_claims=total_claims,
        verified_claims=verified_claims,
        contradiction_links=contradiction_links,
        verdict_breakdown={key: value for key, value in verdict_rows},
        topic_breakdown={key: value for key, value in topic_rows},
    )
