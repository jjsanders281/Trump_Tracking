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
            rationale=(
                "Evidence:\n"
                "- [DEMO] Prior statement in this dataset promises a healthcare plan release within two weeks.\n"
                "- [DEMO] This later statement says no plan release was ever promised.\n"
                "- [DEMO] Both statements are preserved with primary-source links and timestamps.\n\n"
                "Why This Is False:\n"
                "- The later claim denies the existence of a prior promise that is directly documented.\n"
                "- These two claims cannot both be true at the same time on the same subject.\n\n"
                "Shut Down False Argument:\n"
                "- Arguing the promise never happened fails because the earlier quote exists in the record.\n"
                "- Reframing intent does not remove the contradiction between the plain language of both claims."
            ),
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
            rationale=(
                "Evidence:\n"
                "- [DEMO] Official record entry provides the full process language and timeline.\n"
                "- [DEMO] The quoted statement omits qualifying details that appear in the primary record.\n"
                "- [DEMO] Corroborating coverage confirms the full context, not just the clipped excerpt.\n\n"
                "Why This Is False:\n"
                "- The statement presents a partial fact as if it were the whole record.\n"
                "- Missing context changes how a reader would interpret the event and outcome.\n\n"
                "Shut Down False Argument:\n"
                "- Saying the quote is technically accurate is not enough when omitted context reverses meaning.\n"
                "- The complete record, shown in the cited source, resolves the claim against the misleading framing."
            ),
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
