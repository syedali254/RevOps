"""Pydantic schemas for structured AI outputs with evidence validation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SignalType(str, Enum):
    HIRING = "hiring"
    NEWS = "news"
    FUNDING = "funding"
    TECH = "tech"
    EXPANSION = "expansion"
    LEADERSHIP_CHANGE = "leadership_change"
    PRODUCT_LAUNCH = "product_launch"
    PARTNERSHIP = "partnership"
    AWARD = "award"
    REGULATORY = "regulatory"


class ChannelType(str, Enum):
    EMAIL = "email"
    LINKEDIN = "linkedin"
    SMS = "sms"
    PHONE = "phone"
    WEBSITE_FORM = "website_form"


class ResearchProfile(BaseModel):
    """Complete evidence-backed research profile for a company."""
    
    company_summary: str = Field(..., description="2-3 sentence company overview")
    evidence_ids: list[str] = Field(default_factory=list, description="Source record IDs supporting the summary")
    
    signals: list["Signal"] = Field(default_factory=list, description="Business signals with evidence")
    hiring_signals: list["HiringSignal"] = Field(default_factory=list, description="Hiring signals from job boards")
    news_signals: list["NewsSignal"] = Field(default_factory=list, description="News and funding signals")
    tech_signals: list["TechSignal"] = Field(default_factory=list, description="Technology stack signals")
    
    decision_makers: list["DecisionMaker"] = Field(default_factory=list, description="Potential decision makers")
    
    opening: "OpeningDraft" = Field(..., description="Suggested opening line with evidence")
    suggested_questions: list[str] = Field(default_factory=list, description="Two suggested questions for the call")
    
    unknowns: list[str] = Field(default_factory=list, description="Explicitly unknown or unverified facts")
    limitations: list[str] = Field(default_factory=list, description="Research limitations and gaps")
    
    evidence_refs: list[str] = Field(default_factory=list, description="All source record IDs used")
    
    # Metadata
    model_version: str = Field(..., description="Model identifier used")
    prompt_version: str = Field(default="1.0", description="Prompt template version")
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    latency_ms: int = Field(default=0, description="Generation latency in milliseconds")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {"extra": "forbid"}


class Signal(BaseModel):
    """A business signal with evidence."""
    
    claim: str = Field(..., description="The signal claim (e.g., 'Hiring 5+ engineers')")
    type: SignalType = Field(..., description="Type of signal")
    confidence: ConfidenceLevel = Field(..., description="Confidence level")
    evidence_ids: list[str] = Field(default_factory=list, description="Source record IDs")
    source_urls: list[str] = Field(default_factory=list, description="Direct URLs to evidence")
    raw_excerpt: str = Field(default="", description="Short excerpt from source")
    published_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"extra": "forbid"}


class HiringSignal(Signal):
    """Hiring-specific signal with job details."""
    
    type: Literal[SignalType.HIRING] = SignalType.HIRING
    job_titles: list[str] = Field(default_factory=list)
    job_count: int = 0
    departments: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    seniority_levels: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    
    model_config = {"extra": "forbid"}


class NewsSignal(Signal):
    """News/funding signal with article details."""
    
    type: Literal[SignalType.NEWS, SignalType.FUNDING] = Field(...)
    publisher: str = ""
    article_title: str = ""
    article_url: str = ""
    published_at: Optional[datetime] = None
    
    model_config = {"extra": "forbid"}


class TechSignal(Signal):
    """Technology stack signal from website analysis."""
    
    type: Literal[SignalType.TECH] = SignalType.TECH
    technologies: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    source_page: str = ""
    
    model_config = {"extra": "forbid"}


class DecisionMaker(BaseModel):
    """Potential decision maker with verified title."""
    
    name: str = Field(..., description="Full name as found in source")
    title: str = Field(..., description="Title exactly as found in source")
    title_normalized: Optional[str] = Field(None, description="Normalized title for matching")
    profile_url: Optional[str] = Field(None, description="LinkedIn or company bio URL")
    source_url: str = Field(..., description="Source URL where found")
    source_type: str = Field(..., description="Source type (linkedin, company_site, news, etc.)")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.LOW)
    evidence_ids: list[str] = Field(default_factory=list)
    seniority: Optional[str] = Field(None, description="Seniority level if inferable")
    department: Optional[str] = Field(None, description="Department if inferable")
    verified_current: bool = Field(default=False, description="Whether currently verified at company")
    
    model_config = {"extra": "forbid"}


class OpeningDraft(BaseModel):
    """Suggested opening line with evidence backing."""
    
    text: str = Field(..., min_length=10, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    fallback_used: bool = Field(default=False, description="Whether company-level fallback was used")
    personalization_type: Literal["personal", "company_level", "signal_based"] = Field(...)
    evidence_excerpt: str = Field(default="", description="Supporting evidence excerpt")
    
    model_config = {"extra": "forbid"}


class OutreachDraft(BaseModel):
    """Complete outreach draft for a specific channel."""
    
    channel: ChannelType = Field(...)
    recipient_name: Optional[str] = None
    recipient_title: Optional[str] = None
    subject: Optional[str] = Field(None, max_length=200)
    body: str = Field(..., min_length=20)
    
    evidence_refs: list[str] = Field(default_factory=list)
    personalization_reasons: list[str] = Field(default_factory=list)
    
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    fallback_used: bool = False
    
    # Metadata
    channel_specific: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    personalization_reasons: list[str] = Field(default_factory=list)
    
    # Metadata
    version: int = 1
    status: Literal["draft", "approved", "rejected", "sent"] = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    model_name: str = ""
    prompt_version: str = "1.0"
    tokens_used: int = 0
    latency_ms: int = 0
    
    model_config = {"extra": "forbid"}


class SignalAnalysis(BaseModel):
    """Analysis of signals for a company."""
    
    company_id: int
    signals: list[Signal]
    hiring_signals: list[HiringSignal]
    news_signals: list[NewsSignal]
    tech_signals: list[TechSignal]
    summary: str
    strongest_signals: list[Signal]
    evidence_coverage: float = Field(ge=0, le=1)
    
    model_config = {"extra": "forbid"}


class FactVerification(BaseModel):
    """Result of fact verification across sources."""
    
    claim: str
    status: Literal["verified", "conflicting", "unverified", "refuted"]
    supporting_sources: list[str] = Field(default_factory=list)
    conflicting_sources: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    reasoning: str
    evidence_ids: list[str]
    
    model_config = {"extra": "forbid"}


class VerificationResult(BaseModel):
    """Result of multi-source fact verification."""
    
    company_id: int
    verifications: list[FactVerification]
    overall_confidence: ConfidenceLevel
    verified_count: int
    conflicting_count: int
    unverified_count: int
    needs_human_review: bool
    
    model_config = {"extra": "forbid"}


class ResearchQualityMetrics(BaseModel):
    """Quality metrics for generated research."""
    
    total_claims: int
    claims_with_evidence: int
    claims_without_evidence: int
    evidence_coverage: float = Field(ge=0, le=1)
    unique_sources: int
    avg_claims_per_source: float
    hallucination_risk: Literal["low", "medium", "high"]
    
    model_config = {"extra": "forbid"}


class DraftQualityMetrics(BaseModel):
    """Quality metrics for generated draft."""
    
    has_personalization: bool
    personalization_reasons_count: int
    evidence_refs_count: int
    channel_appropriate: bool
    length_appropriate: bool
    has_call_to_action: bool
    uncertainty_marked: bool
    overall_quality: Literal["high", "medium", "low"]
    
    model_config = {"extra": "forbid"}


# Re-export timezone for convenience
from datetime import timezone