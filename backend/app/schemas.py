"""Pydantic request/response models — the typed API boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- campaigns -------------------------------------------------------------


class CampaignSettings(BaseModel):
    """Immutable settings snapshot stored with the campaign."""

    countries: list[str] = Field(default_factory=lambda: ["United States"])
    sectors: list[str] = Field(default_factory=lambda: ["software", "IT services", "data"])
    employee_min: int | None = 20
    employee_max: int | None = 200
    target_titles: list[str] = Field(
        default_factory=lambda: ["Founder", "CEO", "Head of Operations", "Head of IT"]
    )
    exclusions: list[str] = Field(default_factory=list)
    require_domain: bool = True


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    settings: CampaignSettings = Field(default_factory=CampaignSettings)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Campaign name must not be empty")
        return cleaned


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    settings: dict[str, Any]
    settings_version: int
    company_count: int = 0
    run_count: int = 0
    created_at: datetime
    updated_at: datetime


# --- companies -------------------------------------------------------------


class CompanyCreate(BaseModel):
    canonical_name: str = Field(min_length=1, max_length=300)
    website_domain: str | None = None
    country: str | None = None
    sector: str | None = None
    employee_min: int | None = None
    employee_max: int | None = None

    @field_validator("canonical_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Company name must not be empty")
        return cleaned

    @field_validator("website_domain")
    @classmethod
    def clean_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        cleaned = cleaned.removeprefix("https://").removeprefix("http://")
        cleaned = cleaned.split("/")[0]
        return cleaned or None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    canonical_name: str
    website_domain: str | None
    country: str | None
    sector: str | None
    employee_min: int | None
    employee_max: int | None
    record_kind: str
    workflow_status: str
    created_at: datetime
    lead_fit_score: int | None = None
    evidence_confidence: int | None = None
    qualification_status: str | None = None
    qualification_reason: str | None = None
    approval_status: str | None = None
    research_brief: str | None = None
    is_excluded: bool = False
    exclusion_reason: str | None = None


class CompanyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    canonical_name: str
    website_domain: str | None
    country: str | None
    sector: str | None
    employee_min: int | None
    employee_max: int | None
    record_kind: str
    workflow_status: str
    created_at: datetime
    lead_fit_score: int | None = None
    evidence_confidence: int | None = None
    qualification_status: str | None = None


class CompanyDetail(CompanyOut):
    sources: list[SourceRecordOut] = Field(default_factory=list)


# --- workflow runs ---------------------------------------------------------


class RunCreate(BaseModel):
    campaign_id: int
    company_id: int | None = None
    company: CompanyCreate | None = None
    # Test control: force a stage to fail so the failure path can be demonstrated.
    fail_at: Literal["start", "find", "merge", "evaluate"] | None = None

    @model_validator(mode="after")
    def require_company_ref(self) -> "RunCreate":
        if self.company is None and self.company_id is None:
            raise ValueError("Provide either 'company_id' or a new 'company' definition")
        return self


class DiscoveryRunCreate(BaseModel):
    """Start a discovery run for a campaign (finds multiple candidates)."""
    campaign_id: int
    # Optional overrides for this discovery run
    max_results: int | None = None
    fail_at: Literal["start", "find", "merge", "evaluate"] | None = None


class StageEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stage: str
    status: str
    attempt: int
    started_at: datetime
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    details: dict[str, Any] = Field(default_factory=dict)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    campaign_name: str | None = None
    company_id: int | None
    company_name: str | None = None
    run_type: str = "qualification"
    status: str
    outcome: str | None
    review_reason: str | None
    error_code: str | None
    error_message: str | None
    is_test_run: bool
    started_at: datetime
    finished_at: datetime | None
    events: list[StageEventOut] = Field(default_factory=list)


class SourceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int | None
    source_type: str
    provider: str
    source_url: str | None
    retrieved_at: datetime
    published_at: datetime | None
    status: str
    error_message: str | None
    raw_payload: "Any" = Field(default_factory=dict)


class DiscoveryRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campaign_id: int
    campaign_name: str | None = None
    run_type: str = "discovery"
    status: str
    outcome: str | None
    review_reason: str | None
    error_code: str | None
    error_message: str | None
    is_test_run: bool
    started_at: datetime
    finished_at: datetime | None
    events: list[StageEventOut] = Field(default_factory=list)
    companies_discovered: int = 0
    companies_created: int = 0
    duplicates_found: int = 0


# --- overview --------------------------------------------------------------


class SourceHealth(BaseModel):
    key: str
    label: str
    role: str  # discovery | enrichment | both
    provider: str | None
    status: str = "not_configured"
    detail: str


class SafetyOut(BaseModel):
    dry_run: bool
    messages_sent: int
    send_implemented: bool
    banner: str
    detail: str


class OverviewCounts(BaseModel):
    campaigns: int
    companies: int
    test_companies: int
    retrieved_companies: int
    runs: int
    runs_by_status: dict[str, int]


class OverviewOut(BaseModel):
    generated_at: datetime
    counts: OverviewCounts
    safety: SafetyOut
    sources: list[SourceHealth]
    recent_runs: list[RunOut]
    next_actions: list[str]


# Resolve forward references
SourceRecordOut.model_rebuild()
RunOut.model_rebuild()
DiscoveryRunOut.model_rebuild()
StageEventOut.model_rebuild()