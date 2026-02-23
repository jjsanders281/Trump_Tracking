from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

claim_tags = Table(
    "claim_tags",
    Base.metadata,
    Column("claim_id", ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Statement(Base):
    __tablename__ = "statements"
    __table_args__ = (
        CheckConstraint("impact_score >= 1 AND impact_score <= 5", name="ck_statement_impact_score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    speaker: Mapped[str] = mapped_column(String(120), default="Donald J. Trump", index=True)
    venue: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    media_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    region: Mapped[str] = mapped_column(String(64), default="US")
    impact_score: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    claims: Mapped[list[Claim]] = relationship(
        "Claim", back_populates="statement", cascade="all, delete-orphan"
    )


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    statement_id: Mapped[int] = mapped_column(ForeignKey("statements.id", ondelete="CASCADE"), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(120), index=True)
    claim_kind: Mapped[str] = mapped_column(String(64), default="statement")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    statement: Mapped[Statement] = relationship("Statement", back_populates="claims")
    assessments: Mapped[list[Assessment]] = relationship(
        "Assessment", back_populates="claim", cascade="all, delete-orphan", order_by="Assessment.created_at"
    )
    sources: Mapped[list[Source]] = relationship(
        "Source", back_populates="claim", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship("Tag", secondary=claim_tags, back_populates="claims")


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('true', 'mixed', 'misleading', 'false', 'unverified', 'unfulfilled', 'contradicted')",
            name="ck_assessment_verdict",
        ),
        CheckConstraint(
            "publish_status IN ('pending', 'verified', 'rejected')", name="ck_assessment_publish_status"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    verdict: Mapped[str] = mapped_column(String(32), index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_primary: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    reviewer_secondary: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    source_tier_used: Mapped[int] = mapped_column(Integer, default=1)
    publish_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    claim: Mapped[Claim] = relationship("Claim", back_populates="assessments")


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("source_tier >= 1 AND source_tier <= 3", name="ck_source_tier"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    publisher: Mapped[str] = mapped_column(String(120), index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_tier: Mapped[int] = mapped_column(Integer, default=2)
    is_primary: Mapped[bool] = mapped_column(default=False)
    archived_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    claim: Mapped[Claim] = relationship("Claim", back_populates="sources")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)

    claims: Mapped[list[Claim]] = relationship("Claim", secondary=claim_tags, back_populates="tags")


class Contradiction(Base):
    __tablename__ = "contradictions"
    __table_args__ = (UniqueConstraint("claim_id", "contradicts_claim_id", name="uq_contradiction_pair"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    contradicts_claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Revision(Base):
    __tablename__ = "revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    changed_by: Mapped[str] = mapped_column(String(120))
    change_summary: Mapped[str] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
