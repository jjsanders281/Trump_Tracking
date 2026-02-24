from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from . import models, schemas

LIE_VERDICTS = ("false", "misleading", "contradicted")
CURRENT_TERM_START_DATE = date(2025, 1, 20)
CAMPAIGN_LAUNCH_DATE = date(2015, 6, 16)


def _latest_assessment(assessments: list[models.Assessment]) -> Optional[models.Assessment]:
    if not assessments:
        return None
    return sorted(assessments, key=lambda item: (item.verified_at or item.created_at), reverse=True)[0]


def _claim_query_with_relations(db: Session):
    return db.query(models.Claim).options(
        selectinload(models.Claim.statement),
        selectinload(models.Claim.assessments),
        selectinload(models.Claim.sources),
        selectinload(models.Claim.tags),
    )


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


def _get_claim_model(db: Session, claim_id: int) -> Optional[models.Claim]:
    return _claim_query_with_relations(db).filter(models.Claim.id == claim_id).first()


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


def _record_revision(
    db: Session,
    entity_type: str,
    entity_id: int,
    changed_by: str,
    change_summary: str,
) -> None:
    db.add(
        models.Revision(
            entity_type=entity_type,
            entity_id=entity_id,
            changed_by=changed_by,
            change_summary=change_summary,
        )
    )


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
        verified_at = payload.assessment.verified_at
        if payload.assessment.publish_status == "verified" and verified_at is None:
            verified_at = datetime.utcnow()

        db.add(
            models.Assessment(
                claim_id=claim.id,
                verdict=payload.assessment.verdict,
                rationale=payload.assessment.rationale,
                reviewer_primary=payload.assessment.reviewer_primary,
                reviewer_secondary=payload.assessment.reviewer_secondary,
                source_tier_used=payload.assessment.source_tier_used,
                publish_status=payload.assessment.publish_status,
                verified_at=verified_at,
            )
        )
        _record_revision(
            db,
            entity_type="claim",
            entity_id=claim.id,
            changed_by=payload.assessment.reviewer_primary or "system",
            change_summary=(
                f"Claim created with assessment status={payload.assessment.publish_status} "
                f"verdict={payload.assessment.verdict}"
            ),
        )
    else:
        _record_revision(
            db,
            entity_type="claim",
            entity_id=claim.id,
            changed_by="research_agent",
            change_summary="Claim intake created without assessment",
        )

    db.commit()

    return _claim_query_with_relations(db).filter(models.Claim.id == claim.id).one()


def create_intake_claim(db: Session, payload: schemas.IntakeClaimCreate) -> schemas.ClaimRead:
    bundle = schemas.ClaimBundleCreate(
        statement=payload.statement,
        claim=payload.claim,
        sources=payload.sources,
        assessment=None,
    )
    claim = create_claim_bundle(db, bundle)

    if payload.intake_note:
        _record_revision(
            db,
            entity_type="claim",
            entity_id=claim.id,
            changed_by="research_agent",
            change_summary=f"Intake note: {payload.intake_note[:600]}",
        )
        db.commit()

    result = get_claim(db, claim.id)
    return result  # type: ignore[return-value]


def submit_fact_check(
    db: Session,
    claim_id: int,
    payload: schemas.FactCheckSubmission,
) -> schemas.ClaimRead:
    claim = _get_claim_model(db, claim_id)
    if claim is None:
        raise ValueError("Claim not found")

    latest = _latest_assessment(claim.assessments)
    if latest and latest.publish_status in {"verified", "rejected"}:
        raise ValueError("Claim workflow is finalized; reopen flow before new fact-check submission")

    if latest and latest.publish_status == "pending":
        latest.verdict = payload.verdict
        latest.rationale = payload.rationale
        latest.reviewer_primary = payload.reviewer_primary
        latest.source_tier_used = payload.source_tier_used
        latest.verified_at = None
        latest.reviewer_secondary = None
    else:
        db.add(
            models.Assessment(
                claim_id=claim.id,
                verdict=payload.verdict,
                rationale=payload.rationale,
                reviewer_primary=payload.reviewer_primary,
                source_tier_used=payload.source_tier_used,
                publish_status="pending",
                verified_at=None,
            )
        )

    existing_source_urls = {source.url for source in claim.sources}
    for source in payload.sources:
        if source.url in existing_source_urls:
            continue
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

    contradiction_ids = sorted({cid for cid in payload.contradiction_claim_ids if cid != claim.id})
    if contradiction_ids:
        existing_claim_ids = {
            row[0]
            for row in db.query(models.Claim.id)
            .filter(models.Claim.id.in_(contradiction_ids))
            .all()
        }
        missing_ids = [cid for cid in contradiction_ids if cid not in existing_claim_ids]
        if missing_ids:
            raise ValueError(f"Invalid contradiction claim IDs: {missing_ids}")

        existing_pairs = {
            (row.claim_id, row.contradicts_claim_id)
            for row in db.query(models.Contradiction)
            .filter(
                models.Contradiction.claim_id == claim.id,
                models.Contradiction.contradicts_claim_id.in_(contradiction_ids),
            )
            .all()
        }
        for target_id in contradiction_ids:
            if (claim.id, target_id) in existing_pairs:
                continue
            db.add(
                models.Contradiction(
                    claim_id=claim.id,
                    contradicts_claim_id=target_id,
                    note=payload.note,
                )
            )

    summary = f"Fact-check submitted: verdict={payload.verdict}, status=pending"
    if payload.note:
        summary = f"{summary}. Note: {payload.note[:500]}"

    _record_revision(
        db,
        entity_type="claim",
        entity_id=claim.id,
        changed_by=payload.reviewer_primary,
        change_summary=summary,
    )

    db.commit()

    result = get_claim(db, claim.id)
    return result  # type: ignore[return-value]


def submit_editorial_decision(
    db: Session,
    claim_id: int,
    payload: schemas.EditorialDecision,
) -> schemas.ClaimRead:
    claim = _get_claim_model(db, claim_id)
    if claim is None:
        raise ValueError("Claim not found")

    pending_assessments = [item for item in claim.assessments if item.publish_status == "pending"]
    if not pending_assessments:
        raise ValueError("No pending assessment found for this claim")

    latest_pending = sorted(pending_assessments, key=lambda item: item.id, reverse=True)[0]
    latest_pending.publish_status = payload.publish_status
    latest_pending.reviewer_secondary = payload.reviewer_secondary

    if payload.publish_status == "verified":
        latest_pending.verified_at = payload.verified_at or datetime.utcnow()
    else:
        latest_pending.verified_at = None

    summary = f"Editorial decision: {payload.publish_status}"
    if payload.note:
        summary = f"{summary}. Note: {payload.note[:500]}"

    _record_revision(
        db,
        entity_type="claim",
        entity_id=claim.id,
        changed_by=payload.reviewer_secondary,
        change_summary=summary,
    )

    db.commit()

    result = get_claim(db, claim.id)
    return result  # type: ignore[return-value]


def update_claim(
    db: Session,
    claim_id: int,
    payload: schemas.ClaimPatchPayload,
) -> schemas.ClaimRead:
    claim = _get_claim_model(db, claim_id)
    if claim is None:
        raise ValueError("Claim not found")

    changes: list[str] = []

    if payload.claim:
        for field in ("claim_text", "topic", "claim_kind"):
            new_val = getattr(payload.claim, field)
            if new_val is not None:
                old_val = getattr(claim, field)
                if new_val != old_val:
                    setattr(claim, field, new_val)
                    changes.append(f"{field}: {old_val!r} -> {new_val!r}")
        if payload.claim.tags is not None:
            old_tags = sorted(t.name for t in claim.tags)
            claim.tags = _get_or_create_tags(db, payload.claim.tags)
            new_tags = sorted(t.name for t in claim.tags)
            if old_tags != new_tags:
                changes.append(f"tags: {old_tags} -> {new_tags}")

    if payload.statement:
        stmt = claim.statement
        for field in (
            "occurred_at", "speaker", "venue", "quote", "context",
            "primary_source_url", "media_url", "region", "impact_score",
        ):
            new_val = getattr(payload.statement, field)
            if new_val is not None:
                old_val = getattr(stmt, field)
                if new_val != old_val:
                    setattr(stmt, field, new_val)
                    changes.append(f"statement.{field} updated")

    if not changes:
        raise ValueError("No changes detected in payload")

    summary = f"Claim updated: {'; '.join(changes)}"
    if payload.note:
        summary = f"{summary}. Note: {payload.note[:500]}"

    _record_revision(
        db,
        entity_type="claim",
        entity_id=claim.id,
        changed_by=payload.changed_by,
        change_summary=summary,
    )

    db.commit()

    result = get_claim(db, claim.id)
    return result  # type: ignore[return-value]


def replace_sources(
    db: Session,
    claim_id: int,
    payload: schemas.SourcesReplacePayload,
) -> schemas.ClaimRead:
    claim = _get_claim_model(db, claim_id)
    if claim is None:
        raise ValueError("Claim not found")

    old_count = len(claim.sources)
    for source in claim.sources:
        db.delete(source)
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

    summary = f"Sources replaced: {old_count} removed, {len(payload.sources)} added"
    if payload.note:
        summary = f"{summary}. Note: {payload.note[:500]}"

    _record_revision(
        db,
        entity_type="claim",
        entity_id=claim.id,
        changed_by=payload.changed_by,
        change_summary=summary,
    )

    db.commit()

    result = get_claim(db, claim.id)
    return result  # type: ignore[return-value]


def reopen_claim(
    db: Session,
    claim_id: int,
    payload: schemas.ReopenPayload,
) -> schemas.ClaimRead:
    claim = _get_claim_model(db, claim_id)
    if claim is None:
        raise ValueError("Claim not found")

    latest = _latest_assessment(claim.assessments)
    if latest is None:
        raise ValueError("Claim has no assessment to reopen")
    if latest.publish_status == "pending":
        raise ValueError("Claim is already pending; nothing to reopen")

    old_status = latest.publish_status
    latest.publish_status = "pending"
    latest.verified_at = None
    latest.reviewer_secondary = None

    _record_revision(
        db,
        entity_type="claim",
        entity_id=claim.id,
        changed_by=payload.changed_by,
        change_summary=f"Claim reopened from {old_status}. Reason: {payload.reason[:500]}",
    )

    db.commit()

    result = get_claim(db, claim.id)
    return result  # type: ignore[return-value]


def delete_claim(db: Session, claim_id: int) -> bool:
    claim = _get_claim_model(db, claim_id)
    if claim is None:
        raise ValueError("Claim not found")

    # Delete in dependency order
    db.query(models.Contradiction).filter(
        (models.Contradiction.claim_id == claim_id)
        | (models.Contradiction.contradicts_claim_id == claim_id)
    ).delete(synchronize_session=False)
    db.query(models.Revision).filter(
        models.Revision.entity_type == "claim",
        models.Revision.entity_id == claim_id,
    ).delete(synchronize_session=False)
    db.query(models.Assessment).filter(models.Assessment.claim_id == claim_id).delete(
        synchronize_session=False
    )
    db.query(models.Source).filter(models.Source.claim_id == claim_id).delete(
        synchronize_session=False
    )
    # Clear tag associations (many-to-many junction)
    claim.tags = []
    db.flush()

    statement_id = claim.statement_id
    db.delete(claim)
    db.flush()

    # Delete the statement if no other claims reference it
    other_claims = db.query(models.Claim).filter(models.Claim.statement_id == statement_id).count()
    if other_claims == 0:
        stmt = db.query(models.Statement).filter(models.Statement.id == statement_id).first()
        if stmt:
            db.delete(stmt)

    db.commit()
    return True


def get_claim(db: Session, claim_id: int) -> Optional[schemas.ClaimRead]:
    claim = _get_claim_model(db, claim_id)
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

    if needs_assessment_join:
        # Postgres requires ORDER BY columns in SELECT list when using DISTINCT.
        # Use a subquery to get distinct claim IDs, then fetch full objects.
        claim_ids_q = query.with_entities(models.Claim.id, models.Statement.occurred_at).distinct()
        total = claim_ids_q.count()
        id_rows = (
            claim_ids_q
            .order_by(models.Statement.occurred_at.desc(), models.Claim.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        ordered_ids = [row[0] for row in id_rows]
        if ordered_ids:
            claims_unordered = _claim_query_with_relations(db).filter(models.Claim.id.in_(ordered_ids)).all()
            id_order = {cid: idx for idx, cid in enumerate(ordered_ids)}
            claims = sorted(claims_unordered, key=lambda c: id_order[c.id])
        else:
            claims = []
    else:
        total = query.count()
        claims = (
            query.order_by(models.Statement.occurred_at.desc(), models.Claim.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    items = [_serialize_claim(claim) for claim in claims]

    return schemas.ClaimSearchResponse(total=total, limit=limit, offset=offset, items=items)


def _latest_assessment_subquery(db: Session):
    return (
        db.query(
            models.Assessment.claim_id.label("claim_id"),
            func.max(models.Assessment.id).label("assessment_id"),
        )
        .group_by(models.Assessment.claim_id)
        .subquery()
    )


def _workflow_stage_filter(stage: schemas.WorkflowStage, latest_assessment_subq):
    if stage == "fact_check":
        return or_(
            latest_assessment_subq.c.assessment_id.is_(None),
            and_(
                models.Assessment.publish_status == "pending",
                models.Assessment.reviewer_primary.is_(None),
            ),
        )
    if stage == "editorial":
        return and_(
            latest_assessment_subq.c.assessment_id.is_not(None),
            models.Assessment.publish_status == "pending",
            models.Assessment.reviewer_primary.is_not(None),
        )
    if stage == "verified":
        return models.Assessment.publish_status == "verified"
    if stage == "rejected":
        return models.Assessment.publish_status == "rejected"
    raise ValueError(f"Unsupported workflow stage: {stage}")


def workflow_queue(
    db: Session,
    stage: schemas.WorkflowStage,
    limit: int,
    offset: int,
) -> schemas.WorkflowQueueResponse:
    latest_assessment_subq = _latest_assessment_subquery(db)

    id_query = (
        db.query(models.Claim.id, models.Statement.occurred_at)
        .join(models.Statement)
        .outerjoin(latest_assessment_subq, latest_assessment_subq.c.claim_id == models.Claim.id)
        .outerjoin(models.Assessment, models.Assessment.id == latest_assessment_subq.c.assessment_id)
        .filter(_workflow_stage_filter(stage, latest_assessment_subq))
    )

    total = id_query.count()
    id_rows = (
        id_query.order_by(models.Statement.occurred_at.desc(), models.Claim.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    ordered_ids = [row[0] for row in id_rows]

    if ordered_ids:
        claims_unordered = _claim_query_with_relations(db).filter(models.Claim.id.in_(ordered_ids)).all()
        id_order = {cid: idx for idx, cid in enumerate(ordered_ids)}
        claims = sorted(claims_unordered, key=lambda c: id_order[c.id])
    else:
        claims = []

    return schemas.WorkflowQueueResponse(
        stage=stage,
        total=total,
        limit=limit,
        offset=offset,
        items=[_serialize_claim(claim) for claim in claims],
    )


def workflow_queue_summary(db: Session) -> schemas.WorkflowQueueSummary:
    return schemas.WorkflowQueueSummary(
        fact_check=workflow_queue(db, stage="fact_check", limit=1, offset=0).total,
        editorial=workflow_queue(db, stage="editorial", limit=1, offset=0).total,
        verified=workflow_queue(db, stage="verified", limit=1, offset=0).total,
        rejected=workflow_queue(db, stage="rejected", limit=1, offset=0).total,
    )


def _count_lie_claims_since(db: Session, start_date: date) -> int:
    start_dt = datetime.combine(start_date, time.min)
    return (
        db.query(func.count(func.distinct(models.Claim.id)))
        .join(models.Statement, models.Statement.id == models.Claim.statement_id)
        .join(models.Assessment, models.Assessment.claim_id == models.Claim.id)
        .filter(models.Statement.occurred_at >= start_dt)
        .filter(models.Assessment.publish_status == "verified")
        .filter(models.Assessment.verdict.in_(LIE_VERDICTS))
        .scalar()
        or 0
    )


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

    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = date(today.year, 1, 1)

    return schemas.DashboardSummary(
        total_claims=total_claims,
        verified_claims=verified_claims,
        contradiction_links=contradiction_links,
        lie_tracker=schemas.LieTrackerSummary(
            this_week=_count_lie_claims_since(db, week_start),
            this_month=_count_lie_claims_since(db, month_start),
            this_year=_count_lie_claims_since(db, year_start),
            this_term=_count_lie_claims_since(db, CURRENT_TERM_START_DATE),
            since_campaign_launch=_count_lie_claims_since(db, CAMPAIGN_LAUNCH_DATE),
            term_start_date=CURRENT_TERM_START_DATE,
            campaign_launch_date=CAMPAIGN_LAUNCH_DATE,
        ),
        verdict_breakdown={key: value for key, value in verdict_rows},
        topic_breakdown={key: value for key, value in topic_rows},
    )
