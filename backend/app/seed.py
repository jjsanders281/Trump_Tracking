from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from .crud import create_claim_bundle
from .db import Base, SessionLocal, engine
from .models import Claim, Contradiction
from .schemas import AssessmentCreate, ClaimBundleCreate, ClaimCreate, SourceCreate, StatementCreate


DEMO_ENTRIES = [
    ClaimBundleCreate(
        statement=StatementCreate(
            occurred_at=datetime(2024, 10, 1, 14, 0),
            quote="[DEMO] A placeholder campaign statement claims a detailed healthcare plan will be released in two weeks.",
            venue="Campaign Rally",
            primary_source_url="https://example.org/primary-source-healthcare-plan",
            context="Demo data only; replace with verified records.",
            impact_score=3,
        ),
        claim=ClaimCreate(
            claim_text="[DEMO] A full healthcare plan will be released within two weeks.",
            topic="Healthcare",
            claim_kind="promise",
            tags=["healthcare", "promises", "campaign"],
        ),
        sources=[
            SourceCreate(
                publisher="AP",
                url="https://example.org/ap-demo-healthcare",
                source_tier=1,
                is_primary=False,
            )
        ],
        assessment=AssessmentCreate(
            verdict="unfulfilled",
            rationale="[DEMO] This claim is marked unfulfilled for MVP workflow testing.",
            reviewer_primary="demo_researcher",
            reviewer_secondary="demo_editor",
            source_tier_used=1,
            publish_status="verified",
            verified_at=datetime(2024, 11, 15, 9, 30),
        ),
    ),
    ClaimBundleCreate(
        statement=StatementCreate(
            occurred_at=datetime(2025, 2, 1, 10, 0),
            quote="[DEMO] A placeholder statement claims no healthcare plan release was ever promised.",
            venue="Interview",
            primary_source_url="https://example.org/primary-source-denial",
            context="Demo contradiction wiring.",
            impact_score=4,
        ),
        claim=ClaimCreate(
            claim_text="[DEMO] No healthcare plan release was previously promised.",
            topic="Healthcare",
            claim_kind="statement",
            tags=["healthcare", "contradiction", "interview"],
        ),
        sources=[
            SourceCreate(
                publisher="Reuters",
                url="https://example.org/reuters-demo-denial",
                source_tier=1,
                is_primary=False,
            )
        ],
        assessment=AssessmentCreate(
            verdict="contradicted",
            rationale="[DEMO] Earlier documented statement conflicts with this one.",
            reviewer_primary="demo_researcher",
            reviewer_secondary="demo_editor",
            source_tier_used=1,
            publish_status="verified",
            verified_at=datetime(2025, 2, 3, 8, 30),
        ),
    ),
    ClaimBundleCreate(
        statement=StatementCreate(
            occurred_at=datetime(2025, 6, 14, 16, 0),
            quote="[DEMO] A placeholder statement about election processes includes an unsupported assertion.",
            venue="Social Post",
            primary_source_url="https://example.org/primary-source-election-post",
            media_url="https://example.org/video-election-post",
            region="Global",
            impact_score=5,
        ),
        claim=ClaimCreate(
            claim_text="[DEMO] Unsupported assertion about election process integrity.",
            topic="Elections",
            claim_kind="statement",
            tags=["elections", "integrity", "social-media"],
        ),
        sources=[
            SourceCreate(
                publisher="PBS",
                url="https://example.org/pbs-demo-elections",
                source_tier=1,
                is_primary=False,
            ),
            SourceCreate(
                publisher="Official Record",
                url="https://example.org/official-record-demo",
                source_tier=1,
                is_primary=True,
            ),
        ],
        assessment=AssessmentCreate(
            verdict="misleading",
            rationale="[DEMO] Claim omits key context in official records.",
            reviewer_primary="demo_researcher",
            reviewer_secondary="demo_editor",
            source_tier_used=1,
            publish_status="verified",
            verified_at=datetime(2025, 6, 15, 13, 15),
        ),
    ),
]


def seed_demo_data(db: Session) -> None:
    if db.query(Claim).count() > 0:
        return

    created_claim_ids: list[int] = []
    for entry in DEMO_ENTRIES:
        claim = create_claim_bundle(db, entry)
        created_claim_ids.append(claim.id)

    if len(created_claim_ids) >= 2:
        db.add(
            Contradiction(
                claim_id=created_claim_ids[1],
                contradicts_claim_id=created_claim_ids[0],
                note="[DEMO] Later statement conflicts with earlier promise.",
            )
        )
        db.commit()


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_demo_data(session)
    print("Seed complete.")
