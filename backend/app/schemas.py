from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

Verdict = Literal["true", "mixed", "misleading", "false", "unverified", "unfulfilled", "contradicted"]
PublishStatus = Literal["pending", "verified", "rejected"]
WorkflowStage = Literal["fact_check", "editorial", "verified", "rejected"]

HIGH_RISK_VERDICTS = {"false", "misleading", "contradicted"}
HIGH_RISK_RATIONALE_MIN_LENGTH = 240
HIGH_RISK_RATIONALE_SECTIONS = (
    "Evidence:",
    "Why This Is False:",
    "Shut Down False Argument:",
)


def _validate_high_risk_rationale(verdict: Verdict, rationale: str) -> None:
    if verdict not in HIGH_RISK_VERDICTS:
        return

    text = rationale.strip()
    if len(text) < HIGH_RISK_RATIONALE_MIN_LENGTH:
        raise ValueError(
            "High-risk verdict rationale must be detailed (minimum 240 characters) and include sections: "
            "Evidence:, Why This Is False:, Shut Down False Argument:."
        )

    normalized = text.lower()
    missing = [section for section in HIGH_RISK_RATIONALE_SECTIONS if section.lower() not in normalized]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(
            f"High-risk verdict rationale is missing required section(s): {missing_list}"
        )


class StatementCreate(BaseModel):
    occurred_at: datetime
    speaker: str = "Donald J. Trump"
    venue: Optional[str] = None
    quote: str = Field(min_length=5)
    context: Optional[str] = None
    primary_source_url: str
    media_url: Optional[str] = None
    region: str = "US"
    impact_score: int = Field(default=3, ge=1, le=5)


class ClaimCreate(BaseModel):
    claim_text: str = Field(min_length=5)
    topic: str
    claim_kind: str = "statement"
    tags: list[str] = Field(default_factory=list)


class SourceCreate(BaseModel):
    publisher: str
    url: str
    source_tier: int = Field(default=2, ge=1, le=3)
    is_primary: bool = False
    archived_url: Optional[str] = None
    notes: Optional[str] = None


class AssessmentCreate(BaseModel):
    verdict: Verdict
    rationale: str = Field(min_length=10)
    reviewer_primary: Optional[str] = None
    reviewer_secondary: Optional[str] = None
    source_tier_used: int = Field(default=1, ge=1, le=3)
    publish_status: PublishStatus = "verified"
    verified_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_rationale_detail(self) -> "AssessmentCreate":
        _validate_high_risk_rationale(self.verdict, self.rationale)
        return self


class ClaimBundleCreate(BaseModel):
    statement: StatementCreate
    claim: ClaimCreate
    sources: list[SourceCreate] = Field(default_factory=list)
    assessment: Optional[AssessmentCreate] = None


class IntakeClaimCreate(BaseModel):
    statement: StatementCreate
    claim: ClaimCreate
    sources: list[SourceCreate] = Field(default_factory=list)
    intake_note: Optional[str] = None


class FactCheckSubmission(BaseModel):
    verdict: Verdict
    rationale: str = Field(min_length=10)
    reviewer_primary: str = Field(min_length=2)
    source_tier_used: int = Field(default=1, ge=1, le=3)
    sources: list[SourceCreate] = Field(default_factory=list)
    contradiction_claim_ids: list[int] = Field(default_factory=list)
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_rationale_detail(self) -> "FactCheckSubmission":
        _validate_high_risk_rationale(self.verdict, self.rationale)
        return self


class EditorialDecision(BaseModel):
    publish_status: Literal["verified", "rejected"]
    reviewer_secondary: str = Field(min_length=2)
    verified_at: Optional[datetime] = None
    note: Optional[str] = None


class TagRead(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class SourceRead(BaseModel):
    id: int
    publisher: str
    url: str
    source_tier: int
    is_primary: bool
    archived_url: Optional[str]
    notes: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class AssessmentRead(BaseModel):
    id: int
    verdict: Verdict
    rationale: str
    reviewer_primary: Optional[str]
    reviewer_secondary: Optional[str]
    source_tier_used: int
    publish_status: PublishStatus
    verified_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatementRead(BaseModel):
    id: int
    occurred_at: datetime
    speaker: str
    venue: Optional[str]
    quote: str
    context: Optional[str]
    primary_source_url: str
    media_url: Optional[str]
    region: str
    impact_score: int

    model_config = ConfigDict(from_attributes=True)


class ClaimRead(BaseModel):
    id: int
    claim_text: str
    topic: str
    claim_kind: str
    statement: StatementRead
    latest_assessment: Optional[AssessmentRead]
    sources: list[SourceRead]
    tags: list[TagRead]


class ClaimSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ClaimRead]


class LieTrackerSummary(BaseModel):
    this_week: int
    this_month: int
    this_year: int
    this_term: int
    since_campaign_launch: int
    term_start_date: date
    campaign_launch_date: date


class DashboardSummary(BaseModel):
    total_claims: int
    verified_claims: int
    contradiction_links: int
    lie_tracker: LieTrackerSummary
    verdict_breakdown: dict[str, int]
    topic_breakdown: dict[str, int]


class WorkflowQueueResponse(BaseModel):
    stage: WorkflowStage
    total: int
    limit: int
    offset: int
    items: list[ClaimRead]


class WorkflowQueueSummary(BaseModel):
    fact_check: int
    editorial: int
    verified: int
    rejected: int


class ClaimUpdate(BaseModel):
    """Partial update for claim fields. All fields optional — only send what changed."""

    claim_text: Optional[str] = Field(default=None, min_length=5)
    topic: Optional[str] = None
    claim_kind: Optional[str] = None
    tags: Optional[list[str]] = None


class StatementUpdate(BaseModel):
    """Partial update for statement fields. All fields optional — only send what changed."""

    occurred_at: Optional[datetime] = None
    speaker: Optional[str] = None
    venue: Optional[str] = None
    quote: Optional[str] = Field(default=None, min_length=5)
    context: Optional[str] = None
    primary_source_url: Optional[str] = None
    media_url: Optional[str] = None
    region: Optional[str] = None
    impact_score: Optional[int] = Field(default=None, ge=1, le=5)


class ClaimPatchPayload(BaseModel):
    """Combined PATCH payload. Send claim fields, statement fields, or both."""

    claim: Optional[ClaimUpdate] = None
    statement: Optional[StatementUpdate] = None
    changed_by: str = Field(min_length=2)
    note: Optional[str] = None


class SourcesReplacePayload(BaseModel):
    """Replace all sources for a claim. Sends the full desired source list."""

    sources: list[SourceCreate]
    changed_by: str = Field(min_length=2)
    note: Optional[str] = None


class ReopenPayload(BaseModel):
    """Reopen a finalized (verified/rejected) claim for re-review."""

    changed_by: str = Field(min_length=2)
    reason: str = Field(min_length=5)


class DeleteResponse(BaseModel):
    id: int
    deleted: bool
    message: str


class SearchFilters(BaseModel):
    q: Optional[str] = None
    topic: Optional[str] = None
    verdict: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    min_impact: Optional[int] = Field(default=None, ge=1, le=5)
    verified_only: bool = True
