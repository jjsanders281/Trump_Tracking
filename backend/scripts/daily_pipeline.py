#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.crud import create_claim_bundle
from backend.app.db import SessionLocal
from backend.app.schemas import AssessmentCreate, ClaimBundleCreate, ClaimCreate, SourceCreate, StatementCreate

REPO_ROOT = Path(__file__).resolve().parents[2]
INBOX_DIR = REPO_ROOT / "data" / "inbox"


@dataclass
class PipelineStats:
    loaded: int = 0
    accepted: int = 0
    rejected: int = 0
    inserted: int = 0


class ResearchAgent:
    """Collect and normalize raw candidate records into canonical dicts."""

    def load_candidates(self, date_str: str) -> list[dict[str, Any]]:
        inbox_file = INBOX_DIR / f"{date_str}.jsonl"
        if not inbox_file.exists():
            return []

        items: list[dict[str, Any]] = []
        with inbox_file.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        return items


class FactCheckAgent:
    """Applies baseline validation before entries can be persisted."""

    required_fields = {
        "occurred_at",
        "quote",
        "venue",
        "primary_source_url",
        "claim_text",
        "topic",
        "sources",
        "assessment",
    }

    def validate(self, item: dict[str, Any]) -> tuple[bool, str]:
        missing = [field for field in self.required_fields if field not in item]
        if missing:
            return False, f"Missing fields: {', '.join(sorted(missing))}"

        sources = item.get("sources", [])
        if not isinstance(sources, list) or not sources:
            return False, "At least one corroborating source is required"

        assessment = item.get("assessment", {})
        if assessment.get("publish_status") != "verified":
            return False, "Only verified entries are published in this pipeline"

        if not any(source.get("source_tier", 3) <= 2 for source in sources):
            return False, "At least one source must be tier 1 or tier 2"

        return True, "ok"


class DatabaseAgent:
    """Writes validated entries into the application database."""

    def to_bundle(self, item: dict[str, Any]) -> ClaimBundleCreate:
        statement = StatementCreate(
            occurred_at=item["occurred_at"],
            speaker=item.get("speaker", "Donald J. Trump"),
            venue=item["venue"],
            quote=item["quote"],
            context=item.get("context"),
            primary_source_url=item["primary_source_url"],
            media_url=item.get("media_url"),
            region=item.get("region", "US"),
            impact_score=item.get("impact_score", 3),
        )

        claim = ClaimCreate(
            claim_text=item["claim_text"],
            topic=item["topic"],
            claim_kind=item.get("claim_kind", "statement"),
            tags=item.get("tags", []),
        )

        sources = [SourceCreate(**source) for source in item["sources"]]
        assessment = AssessmentCreate(**item["assessment"])

        return ClaimBundleCreate(statement=statement, claim=claim, sources=sources, assessment=assessment)

    def insert_many(self, payloads: list[dict[str, Any]], dry_run: bool) -> int:
        if dry_run:
            return len(payloads)

        inserted = 0
        with SessionLocal() as session:
            for item in payloads:
                bundle = self.to_bundle(item)
                create_claim_bundle(session, bundle)
                inserted += 1
        return inserted


class PipelineOrchestrator:
    """
    Role-based orchestration that can later be split into dedicated AI agents.

    Current role mapping:
    - ResearchAgent: ingest raw candidate records
    - FactCheckAgent: enforce verification rules
    - DatabaseAgent: persist verified entries
    """

    def __init__(self) -> None:
        self.research_agent = ResearchAgent()
        self.fact_check_agent = FactCheckAgent()
        self.database_agent = DatabaseAgent()

    def run(self, date_str: str, dry_run: bool = False) -> PipelineStats:
        stats = PipelineStats()

        raw_items = self.research_agent.load_candidates(date_str)
        stats.loaded = len(raw_items)

        accepted: list[dict[str, Any]] = []
        for item in raw_items:
            ok, reason = self.fact_check_agent.validate(item)
            if not ok:
                stats.rejected += 1
                print(f"REJECTED: {reason} | quote={item.get('quote', '')[:80]}")
                continue
            accepted.append(item)
            stats.accepted += 1

        stats.inserted = self.database_agent.insert_many(accepted, dry_run=dry_run)
        return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run daily verified-entry ingestion pipeline")
    parser.add_argument(
        "--date",
        default=datetime.utcnow().strftime("%Y-%m-%d"),
        help="Date key for inbox file (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; do not write to database",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    orchestrator = PipelineOrchestrator()
    stats = orchestrator.run(date_str=args.date, dry_run=args.dry_run)

    print("Pipeline run complete")
    print(f"  loaded:   {stats.loaded}")
    print(f"  accepted: {stats.accepted}")
    print(f"  rejected: {stats.rejected}")
    print(f"  inserted: {stats.inserted}")


if __name__ == "__main__":
    main()
