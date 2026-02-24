#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from backend.app.crud import create_claim_bundle
from backend.app.db import SessionLocal
from backend.app.schemas import AssessmentCreate, ClaimBundleCreate, ClaimCreate, SourceCreate, StatementCreate

REPO_ROOT = Path(__file__).resolve().parents[2]
INBOX_DIR = REPO_ROOT / "data" / "inbox"

PipelineMode = Literal["current", "backlog"]


@dataclass
class PipelineStats:
    mode: PipelineMode
    files_scanned: int = 0
    loaded: int = 0
    accepted: int = 0
    rejected: int = 0
    inserted: int = 0


class ResearchAgent:
    """Collect and normalize raw candidate records into canonical dicts."""

    def _load_file(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists() or not path.is_file():
            return []

        items: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        return items

    def load_candidates(
        self,
        mode: PipelineMode,
        date_str: str,
        batch_file: Optional[str],
        max_items: Optional[int],
    ) -> tuple[list[dict[str, Any]], int]:
        files: list[Path] = []

        if mode == "current":
            files.append(INBOX_DIR / "current" / f"{date_str}.jsonl")
            # Backward compatibility with older inbox layout.
            files.append(INBOX_DIR / f"{date_str}.jsonl")
        else:
            backlog_dir = INBOX_DIR / "backlog"
            if batch_file:
                files.append(backlog_dir / batch_file)
            elif backlog_dir.exists():
                files.extend(sorted(backlog_dir.glob("*.jsonl")))

        deduped_files = []
        seen = set()
        for file_path in files:
            key = str(file_path.resolve()) if file_path.exists() else str(file_path)
            if key in seen:
                continue
            seen.add(key)
            deduped_files.append(file_path)

        items: list[dict[str, Any]] = []
        for file_path in deduped_files:
            items.extend(self._load_file(file_path))
            if max_items is not None and len(items) >= max_items:
                items = items[:max_items]
                break

        return items, len(deduped_files)


class FactCheckAgent:
    """Applies baseline validation before entries can be persisted."""

    common_required_fields = {
        "occurred_at",
        "quote",
        "venue",
        "primary_source_url",
        "claim_text",
        "topic",
    }

    def validate(self, item: dict[str, Any], mode: PipelineMode) -> tuple[bool, str]:
        missing = [field for field in self.common_required_fields if field not in item]
        if missing:
            return False, f"Missing fields: {', '.join(sorted(missing))}"

        sources = item.get("sources", [])
        if sources is None:
            sources = []
        if not isinstance(sources, list):
            return False, "sources must be a list"

        assessment = item.get("assessment")

        if mode == "current":
            if not sources:
                return False, "Current pipeline requires corroborating sources"
            if not any(source.get("source_tier", 3) <= 2 for source in sources):
                return False, "Current pipeline requires at least one tier 1 or tier 2 source"
            if not assessment:
                return False, "Current pipeline requires an assessment object"
            if assessment.get("publish_status") not in {"pending", "verified"}:
                return False, "Current pipeline accepts assessment status pending or verified"
            return True, "ok"

        # Backlog mode: allow intake-only entries (no assessment yet), but if assessment
        # is present it must use a valid publish status.
        if assessment and assessment.get("publish_status") not in {"pending", "verified", "rejected"}:
            return False, "Backlog assessment publish_status must be pending, verified, or rejected"

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

        sources = [SourceCreate(**source) for source in item.get("sources", [])]

        raw_assessment = item.get("assessment")
        assessment = AssessmentCreate(**raw_assessment) if raw_assessment else None

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
    Role-based orchestration that supports two operational modes:

    - current: daily intake for current/future events, stricter and faster publication
    - backlog: historical catch-up where intake without full assessment is allowed
    """

    def __init__(self) -> None:
        self.research_agent = ResearchAgent()
        self.fact_check_agent = FactCheckAgent()
        self.database_agent = DatabaseAgent()

    def run(
        self,
        mode: PipelineMode,
        date_str: str,
        batch_file: Optional[str],
        max_items: Optional[int],
        dry_run: bool = False,
    ) -> PipelineStats:
        stats = PipelineStats(mode=mode)

        raw_items, files_scanned = self.research_agent.load_candidates(
            mode=mode,
            date_str=date_str,
            batch_file=batch_file,
            max_items=max_items,
        )
        stats.files_scanned = files_scanned
        stats.loaded = len(raw_items)

        accepted: list[dict[str, Any]] = []
        for item in raw_items:
            ok, reason = self.fact_check_agent.validate(item, mode)
            if not ok:
                stats.rejected += 1
                print(f"REJECTED: {reason} | quote={item.get('quote', '')[:80]}")
                continue
            accepted.append(item)
            stats.accepted += 1

        stats.inserted = self.database_agent.insert_many(accepted, dry_run=dry_run)
        return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ingestion pipeline for current or backlog flows")
    parser.add_argument(
        "--mode",
        choices=["current", "backlog"],
        default="current",
        help="Pipeline mode: current (daily) or backlog (historical catch-up)",
    )
    parser.add_argument(
        "--date",
        default=datetime.utcnow().strftime("%Y-%m-%d"),
        help="Date key for current-mode inbox file (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--batch-file",
        default=None,
        help="Backlog mode: optional file name under data/inbox/backlog/",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Optional cap for large backlog runs",
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
    stats = orchestrator.run(
        mode=args.mode,
        date_str=args.date,
        batch_file=args.batch_file,
        max_items=args.max_items,
        dry_run=args.dry_run,
    )

    print("Pipeline run complete")
    print(f"  mode:         {stats.mode}")
    print(f"  files_scanned:{stats.files_scanned}")
    print(f"  loaded:       {stats.loaded}")
    print(f"  accepted:     {stats.accepted}")
    print(f"  rejected:     {stats.rejected}")
    print(f"  inserted:     {stats.inserted}")


if __name__ == "__main__":
    main()
