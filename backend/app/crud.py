from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
import re
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from . import models, schemas

LIE_VERDICTS = ("false", "misleading", "contradicted")
CURRENT_TERM_START_DATE = date(2025, 1, 20)
CAMPAIGN_LAUNCH_DATE = date(2015, 6, 16)
RESEARCH_COVERAGE_DEFAULT_START_DATE = CAMPAIGN_LAUNCH_DATE
RESEARCH_LEVEL_SCORES: dict[str, int] = {
    "missing": 0,
    "researched_no_claim": 25,
    "intake": 40,
    "fact_checked": 70,
    "editorial_reviewed": 85,
    "published": 100,
}
RESEARCH_LEVEL_ORDER = (
    "missing",
    "researched_no_claim",
    "intake",
    "fact_checked",
    "editorial_reviewed",
    "published",
)
RESEARCH_COMPLETE_LEVELS = {"researched_no_claim", "published"}
RESEARCH_IN_PROGRESS_LEVELS = {"intake", "fact_checked", "editorial_reviewed"}
_ISO_DATE_STEM_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

TOPIC_DOSSIER_METADATA: dict[str, dict[str, str]] = {
    "2020-election-stolen": {
        "title": 'The "2020 Election Was Stolen" Lie',
        "summary_prefix": (
            "This dossier tracks repeated versions of the claim that the 2020 U.S. "
            "presidential election was rigged or stolen."
        ),
    }
}

RATIONALE_HEADING_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9 \"'()/-]{2,80}:$")
BULLET_LINE_PATTERN = re.compile(r"^[-*•]\s+")
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")

REPO_ROOT = Path(__file__).resolve().parents[2]
INBOX_DIR = REPO_ROOT / "data" / "inbox"


def _slugify(value: str) -> str:
    slug = _SLUG_PATTERN.sub("-", value.strip().lower()).strip("-")
    return slug or "unknown"


def _claim_tags_lower(claim: models.Claim) -> set[str]:
    return {tag.name.strip().lower() for tag in claim.tags if tag.name.strip()}


def _is_2020_election_stolen_variant(claim: models.Claim) -> bool:
    topic_slug = _slugify(claim.topic)
    if topic_slug != "elections":
        return False
    tags = _claim_tags_lower(claim)
    if "2020-election" not in tags:
        return False

    claim_text = f"{claim.claim_text} {claim.statement.quote}".lower()
    keywords = (
        "stolen",
        "rigged",
        "fraud",
        "dead people",
        "votes changed",
        "vote dump",
        "ballot dump",
        "no vote watchers",
        "observers",
    )
    return any(keyword in claim_text for keyword in keywords)


def _canonical_topic_slug(claim: models.Claim) -> str:
    if _is_2020_election_stolen_variant(claim):
        return "2020-election-stolen"
    return _slugify(claim.topic)


def _parse_rationale_sections(rationale: str) -> dict[str, str]:
    text = rationale.strip()
    if not text:
        return {}

    sections: dict[str, str] = {}
    current_title = "Rationale"
    body_lines: list[str] = []

    for line in text.splitlines():
        trimmed = line.strip()
        if RATIONALE_HEADING_PATTERN.match(trimmed):
            body = "\n".join(body_lines).strip()
            if body:
                sections[current_title] = body
            current_title = trimmed[:-1]
            body_lines = []
            continue
        body_lines.append(line)

    trailing = "\n".join(body_lines).strip()
    if trailing:
        sections[current_title] = trailing
    return sections


def _extract_points(text: str) -> list[str]:
    points: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if BULLET_LINE_PATTERN.match(line):
            line = BULLET_LINE_PATTERN.sub("", line).strip()
        points.append(line)
    return points


def _collect_topic_points(
    claims: list[models.Claim],
    include_if_heading_contains: tuple[str, ...],
    limit: int,
) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()

    for claim in claims:
        latest = _latest_assessment(claim.assessments)
        if latest is None or latest.publish_status != "verified":
            continue
        sections = _parse_rationale_sections(latest.rationale)
        for heading, body in sections.items():
            heading_lc = heading.lower()
            if not any(token in heading_lc for token in include_if_heading_contains):
                continue
            for point in _extract_points(body):
                normalized = " ".join(point.lower().split())
                if normalized in seen:
                    continue
                seen.add(normalized)
                points.append(point)
                if len(points) >= limit:
                    return points
    return points


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
        canonical_topic_slug=_canonical_topic_slug(claim),
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


def _safe_percent(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 1)


def _iter_dates(start_date: date, end_date: date):
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def _parse_exact_iso_date(label: str) -> Optional[date]:
    trimmed = label.strip()
    if not _ISO_DATE_STEM_PATTERN.match(trimmed):
        return None
    try:
        return date.fromisoformat(trimmed)
    except ValueError:
        return None


def _count_jsonl_lines(path: Path) -> int:
    count = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if raw.strip():
                    count += 1
    except OSError:
        return 0
    return count


def _load_inbox_research_markers() -> tuple[dict[date, int], set[date]]:
    """
    Build per-day research markers from inbox files.

    candidate_counts:
      day -> number of non-empty JSONL entries found in daily inbox files.
    no_claim_dates:
      day -> exists a daily `.no-claim.md` research note.
    """
    candidate_counts: dict[date, int] = {}
    no_claim_dates: set[date] = set()

    for directory in (INBOX_DIR / "current", INBOX_DIR / "backlog", INBOX_DIR):
        if not directory.exists() or not directory.is_dir():
            continue

        for jsonl_file in directory.glob("*.jsonl"):
            day = _parse_exact_iso_date(jsonl_file.stem)
            if day is None:
                continue
            count = _count_jsonl_lines(jsonl_file)
            if count <= 0:
                continue
            candidate_counts[day] = max(candidate_counts.get(day, 0), count)

        for note_file in directory.glob("*.no-claim.md"):
            token = note_file.name[: -len(".no-claim.md")]
            day = _parse_exact_iso_date(token)
            if day is not None:
                no_claim_dates.add(day)

    return candidate_counts, no_claim_dates


def _research_level_for_day(
    claim_count: int,
    intake_candidate_count: int,
    fact_checked_claim_count: int,
    editorial_claim_count: int,
    finalized_claim_count: int,
    has_no_claim_note: bool,
) -> schemas.ResearchCoverageLevel:
    if claim_count <= 0:
        if intake_candidate_count > 0:
            return "intake"
        if has_no_claim_note:
            return "researched_no_claim"
        return "missing"

    if finalized_claim_count >= claim_count:
        return "published"
    if editorial_claim_count > 0:
        return "editorial_reviewed"
    if fact_checked_claim_count > 0:
        return "fact_checked"
    return "intake"


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


def _topic_dossier_title(slug: str, claims: list[models.Claim]) -> str:
    metadata = TOPIC_DOSSIER_METADATA.get(slug)
    if metadata and metadata.get("title"):
        return metadata["title"]
    topic_label = claims[0].topic if claims else slug.replace("-", " ").title()
    return f"{topic_label} Lie Dossier"


def _topic_dossier_summary(
    slug: str,
    total_claims: int,
    first_seen: datetime,
    last_seen: datetime,
    verified_lie_count: int,
) -> str:
    prefix = TOPIC_DOSSIER_METADATA.get(slug, {}).get("summary_prefix", "")
    summary = (
        f"This page aggregates {total_claims} recorded claim instance(s) from "
        f"{first_seen.date().isoformat()} through {last_seen.date().isoformat()}. "
        f"{verified_lie_count} instance(s) are currently verified with verdicts "
        "marked false, misleading, or contradicted."
    )
    if prefix:
        return f"{prefix} {summary}"
    return summary


def topic_page(
    db: Session,
    topic_slug: str,
    limit: int,
) -> Optional[schemas.TopicPageRead]:
    normalized_slug = _slugify(topic_slug)
    all_claims = (
        _claim_query_with_relations(db)
        .join(models.Statement)
        .order_by(models.Statement.occurred_at.desc(), models.Claim.id.desc())
        .all()
    )

    matching = [claim for claim in all_claims if _canonical_topic_slug(claim) == normalized_slug]
    if not matching:
        matching = [
            claim
            for claim in all_claims
            if _slugify(claim.topic) == normalized_slug
            or normalized_slug in {_slugify(tag.name) for tag in claim.tags}
        ]
    if not matching:
        return None

    first_seen = min(claim.statement.occurred_at for claim in matching)
    last_seen = max(claim.statement.occurred_at for claim in matching)
    total_claims = len(matching)

    verified_lie_count = 0
    for claim in matching:
        latest = _latest_assessment(claim.assessments)
        if latest and latest.publish_status == "verified" and latest.verdict in LIE_VERDICTS:
            verified_lie_count += 1

    tag_counts: dict[str, int] = {}
    source_index: dict[str, dict[str, object]] = {}
    for claim in matching:
        for tag in claim.tags:
            tag_counts[tag.name] = tag_counts.get(tag.name, 0) + 1

        for source in claim.sources:
            if not source.url:
                continue
            entry = source_index.setdefault(
                source.url,
                {
                    "publisher": source.publisher,
                    "url": source.url,
                    "source_tier": source.source_tier,
                    "is_primary": bool(source.is_primary),
                    "supporting_claim_ids": set(),
                    "notes": source.notes or "",
                },
            )
            entry["source_tier"] = min(int(entry["source_tier"]), int(source.source_tier))
            entry["is_primary"] = bool(entry["is_primary"]) or bool(source.is_primary)
            cast_claim_ids: set[int] = entry["supporting_claim_ids"]  # type: ignore[assignment]
            cast_claim_ids.add(claim.id)
            if not entry["notes"] and source.notes:
                entry["notes"] = source.notes

        primary_url = claim.statement.primary_source_url
        if primary_url:
            entry = source_index.setdefault(
                primary_url,
                {
                    "publisher": "Primary statement record",
                    "url": primary_url,
                    "source_tier": 1,
                    "is_primary": True,
                    "supporting_claim_ids": set(),
                    "notes": "Original statement or transcript source.",
                },
            )
            cast_claim_ids: set[int] = entry["supporting_claim_ids"]  # type: ignore[assignment]
            cast_claim_ids.add(claim.id)

    sources = [
        schemas.TopicSourceRead(
            publisher=str(payload["publisher"]),
            url=str(payload["url"]),
            source_tier=int(payload["source_tier"]),
            is_primary=bool(payload["is_primary"]),
            supporting_claim_ids=sorted(payload["supporting_claim_ids"]),  # type: ignore[arg-type]
            notes=str(payload["notes"]) if payload.get("notes") else None,
        )
        for payload in source_index.values()
    ]
    sources.sort(key=lambda item: (not item.is_primary, item.source_tier, item.publisher.lower()))

    key_evidence_points = _collect_topic_points(
        matching,
        include_if_heading_contains=("evidence", "why this is false"),
        limit=12,
    )
    if not key_evidence_points:
        key_evidence_points = [
            (
                "Official records tied to this topic are linked below; see statement "
                "sources, election boards, and certification documents."
            )
        ]

    shut_down_points = _collect_topic_points(
        matching,
        include_if_heading_contains=("shut down", "counterargument"),
        limit=10,
    )
    if not shut_down_points:
        shut_down_points = [
            (
                "The claim is not supported by official records; use the linked primary "
                "documents to verify the timeline and certified outcomes."
            )
        ]

    related_tags = [
        tag for tag, _count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:16]
    ]

    serialized_claims = [_serialize_claim(claim) for claim in matching[:limit]]
    title = _topic_dossier_title(normalized_slug, matching)
    summary = _topic_dossier_summary(
        normalized_slug,
        total_claims=total_claims,
        first_seen=first_seen,
        last_seen=last_seen,
        verified_lie_count=verified_lie_count,
    )

    return schemas.TopicPageRead(
        slug=normalized_slug,
        title=title,
        summary=summary,
        first_seen=first_seen,
        last_seen=last_seen,
        total_claims=total_claims,
        verified_lie_count=verified_lie_count,
        key_evidence_points=key_evidence_points,
        shut_down_points=shut_down_points,
        related_tags=related_tags,
        claims=serialized_claims,
        sources=sources,
    )


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


def research_coverage_summary(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    missing_limit: int = 45,
    recent_days_limit: int = 60,
) -> schemas.ResearchCoverageSummaryRead:
    range_start = start_date or RESEARCH_COVERAGE_DEFAULT_START_DATE
    range_end = end_date or datetime.utcnow().date()

    if range_start > range_end:
        raise ValueError("start_date cannot be after end_date")

    range_start_dt = datetime.combine(range_start, time.min)
    range_end_dt = datetime.combine(range_end, time.max)

    claims = (
        _claim_query_with_relations(db)
        .join(models.Statement)
        .filter(models.Statement.occurred_at >= range_start_dt)
        .filter(models.Statement.occurred_at <= range_end_dt)
        .all()
    )

    claims_by_day: dict[date, list[models.Claim]] = defaultdict(list)
    for claim in claims:
        claims_by_day[claim.statement.occurred_at.date()].append(claim)

    inbox_candidate_counts, no_claim_dates = _load_inbox_research_markers()

    daily_rows: list[schemas.ResearchDayCoverageRead] = []
    level_breakdown = {level: 0 for level in RESEARCH_LEVEL_ORDER}

    for day in _iter_dates(range_start, range_end):
        day_claims = claims_by_day.get(day, [])
        claim_count = len(day_claims)

        fact_checked_claim_count = 0
        editorial_claim_count = 0
        finalized_claim_count = 0
        verified_lie_count = 0
        corroborating_source_count = 0
        tier1_source_count = 0

        for claim in day_claims:
            corroborating_source_count += len(claim.sources)
            tier1_source_count += sum(1 for source in claim.sources if source.source_tier == 1)

            latest = _latest_assessment(claim.assessments)
            if latest is None:
                continue

            fact_checked_claim_count += 1

            if latest.reviewer_secondary or latest.publish_status in {"verified", "rejected"}:
                editorial_claim_count += 1

            if latest.publish_status in {"verified", "rejected"}:
                finalized_claim_count += 1

            if latest.publish_status == "verified" and latest.verdict in LIE_VERDICTS:
                verified_lie_count += 1

        intake_candidate_count = 0 if claim_count > 0 else inbox_candidate_counts.get(day, 0)
        has_no_claim_note = bool(claim_count == 0 and intake_candidate_count == 0 and day in no_claim_dates)

        level = _research_level_for_day(
            claim_count=claim_count,
            intake_candidate_count=intake_candidate_count,
            fact_checked_claim_count=fact_checked_claim_count,
            editorial_claim_count=editorial_claim_count,
            finalized_claim_count=finalized_claim_count,
            has_no_claim_note=has_no_claim_note,
        )
        level_breakdown[level] = level_breakdown.get(level, 0) + 1

        display_claim_count = claim_count if claim_count > 0 else intake_candidate_count

        daily_rows.append(
            schemas.ResearchDayCoverageRead(
                date=day,
                level=level,
                completion_score=RESEARCH_LEVEL_SCORES.get(level, 0),
                claim_count=display_claim_count,
                fact_checked_claim_count=fact_checked_claim_count,
                editorial_claim_count=editorial_claim_count,
                finalized_claim_count=finalized_claim_count,
                verified_lie_count=verified_lie_count,
                corroborating_source_count=corroborating_source_count,
                tier1_source_count=tier1_source_count,
                has_no_claim_note=has_no_claim_note,
            )
        )

    total_days = len(daily_rows)
    missing_days = sum(1 for row in daily_rows if row.level == "missing")
    researched_days = total_days - missing_days
    complete_days = sum(1 for row in daily_rows if row.level in RESEARCH_COMPLETE_LEVELS)
    in_progress_days = sum(1 for row in daily_rows if row.level in RESEARCH_IN_PROGRESS_LEVELS)

    oldest_missing_dates = [row.date for row in daily_rows if row.level == "missing"][:missing_limit]
    oldest_incomplete_dates = [
        row.date
        for row in daily_rows
        if row.level == "missing" or row.level in RESEARCH_IN_PROGRESS_LEVELS
    ][:missing_limit]

    recent_days = list(reversed(daily_rows))[:recent_days_limit]

    monthly_rollup_raw: dict[str, dict[str, int]] = {}
    for row in daily_rows:
        month_key = row.date.strftime("%Y-%m")
        bucket = monthly_rollup_raw.setdefault(
            month_key,
            {"total_days": 0, "researched_days": 0, "complete_days": 0, "missing_days": 0},
        )
        bucket["total_days"] += 1
        if row.level != "missing":
            bucket["researched_days"] += 1
        if row.level in RESEARCH_COMPLETE_LEVELS:
            bucket["complete_days"] += 1
        if row.level == "missing":
            bucket["missing_days"] += 1

    monthly_rollup = []
    for month_key in sorted(monthly_rollup_raw.keys(), reverse=True):
        bucket = monthly_rollup_raw[month_key]
        monthly_rollup.append(
            schemas.ResearchCoverageMonthRead(
                month=month_key,
                total_days=bucket["total_days"],
                researched_days=bucket["researched_days"],
                complete_days=bucket["complete_days"],
                missing_days=bucket["missing_days"],
                coverage_percent=_safe_percent(bucket["researched_days"], bucket["total_days"]),
                completion_percent=_safe_percent(bucket["complete_days"], bucket["total_days"]),
            )
        )

    return schemas.ResearchCoverageSummaryRead(
        range_start=range_start,
        range_end=range_end,
        total_days=total_days,
        researched_days=researched_days,
        complete_days=complete_days,
        missing_days=missing_days,
        in_progress_days=in_progress_days,
        coverage_percent=_safe_percent(researched_days, total_days),
        completion_percent=_safe_percent(complete_days, total_days),
        level_breakdown=level_breakdown,
        oldest_missing_dates=oldest_missing_dates,
        oldest_incomplete_dates=oldest_incomplete_dates,
        recent_days=recent_days,
        monthly_rollup=monthly_rollup,
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
