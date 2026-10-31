"""SQLAlchemy models.

Milestone 1 keeps the schema small on purpose:
campaigns, companies, source/evidence records, workflow runs and stage events.
Tables are added only when a milestone actually needs them.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    # Immutable settings snapshot for this campaign (sector, country, size, titles...)
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    settings_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    companies: Mapped[list["Company"]] = relationship(back_populates="campaign")
    runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="campaign")

    @property
    def settings(self) -> dict:
        try:
            return json.loads(self.settings_json or "{}")
        except json.JSONDecodeError:
            return {}


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    website_domain: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(200), nullable=True)
    employee_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employee_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # "test_seed" = clearly marked test record entered by a user.
    # "retrieved" = produced by a real source connector (later milestones).
    record_kind: Mapped[str] = mapped_column(String(40), default="test_seed", nullable=False)
    workflow_status: Mapped[str] = mapped_column(String(40), default="discovered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Scoring and qualification
    lead_fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    qualification_status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # qualified, needs_review, rejected
    qualification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    scoring_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Human approval
    approval_status: Mapped[str | None] = mapped_column(String(40), nullable=True)  # pending, approved, rejected
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Research brief
    research_brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    research_model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Safety/Hard exclusions
    is_excluded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # "test_seed" = clearly marked test record entered by a user.
    # "retrieved" = produced by a real source connector (later milestones).
    record_kind: Mapped[str] = mapped_column(String(40), default="test_seed", nullable=False)
    workflow_status: Mapped[str] = mapped_column(String(40), default="discovered")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    campaign: Mapped[Campaign] = relationship(back_populates="companies")
    source_records: Mapped[list["SourceRecord"]] = relationship(back_populates="company")


class SourceRecord(Base):
    """One retrieved (or explicitly attempted) source observation.

    This is the evidence table for Milestone 1. Every externally sourced fact in
    later milestones must point back to a row here so it can keep its URL and
    retrieval timestamp.
    """

    __tablename__ = "source_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    provider: Mapped[str] = mapped_column(String(60), nullable=False, default="manual")
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # success_with_results | success_empty | not_configured | unsupported | failed
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="success_empty")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    company: Mapped[Company | None] = relationship(back_populates="source_records")


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # "discovery" = finds multiple candidates from sources
    # "qualification" = evaluates a single company through the full pipeline
    # "enrichment" = enriches already-discovered companies
    run_type: Mapped[str] = mapped_column(String(40), default="qualification", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="running", nullable=False)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_test_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped[Campaign] = relationship(back_populates="runs")
    company: Mapped["Company | None"] = relationship(foreign_keys=[company_id])
    events: Mapped[list["StageEvent"]] = relationship(
        back_populates="run", order_by="StageEvent.id", cascade="all, delete-orphan"
    )


class StageEvent(Base):
    __tablename__ = "stage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ok")
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped[WorkflowRun] = relationship(back_populates="events")

    @property
    def details(self) -> dict:
        try:
            return json.loads(self.details_json or "{}")
        except json.JSONDecodeError:
            return {}
