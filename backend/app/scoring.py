"""Deterministic lead scoring with factor breakdown and confidence.

This module implements transparent, deterministic lead scoring per the specification:
- Company fit (0-40): Does the company match campaign requirements?
- Evidence quality (0-25): Source reliability, freshness, corroboration, factual support
- Business relevance (0-20): News, hiring, business signals
- Contactability (0-15): Availability of legitimate contact route

Confidence is kept separate from fit. Hard exclusions override scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any

from .models import Company, Campaign
from .db import session_scope
from .models import SourceRecord


@dataclass
class ScoreFactor:
    """Individual scoring factor with breakdown."""
    name: str
    max_points: int
    earned_points: int
    explanation: str
    evidence_refs: list[str]


@dataclass
class ScoreResult:
    """Complete scoring result with breakdown."""
    total_score: int  # 0-100
    factors: list[ScoreFactor]
    confidence: int  # 0-100, separate from fit
    qualification_status: str  # qualified, needs_review, rejected
    qualification_reason: str | None
    hard_exclusions: list[str]
    requires_human_review: bool
    scored_at: datetime
    scoring_version: int = 1


# Default scoring weights (configurable via campaign settings)
DEFAULT_WEIGHTS = {
    "company_fit": 40,
    "evidence_quality": 25,
    "business_relevance": 20,
    "contactability": 15,
}

# Default qualification thresholds
DEFAULT_THRESHOLDS = {
    "high_priority": 75,
    "review_threshold": 50,
    "low_priority": 50,
}


def calculate_company_fit(company: Company, campaign: 'Campaign') -> tuple[int, str, list[str]]:
    """Calculate company fit score (0-40).
    
    Returns: (points_earned, explanation, evidence_refs)
    """
    points = 0
    explanations = []
    evidence_refs = []

    settings = campaign.settings if campaign else {}
    max_points = DEFAULT_WEIGHTS["company_fit"]

    # Sector/industry match (0-15)
    sector_points = 0
    sectors = [s.strip().lower() for s in settings.get("sectors", []) if s.strip()]
    if sectors and company.sector:
        company_sector = company.sector.lower()
        if any(s in company_sector for s in sectors):
            sector_points = 15
            explanations.append(f"Sector '{company.sector}' matches campaign sectors: {', '.join(sectors)}")
        else:
            explanations.append(f"Sector '{company.sector}' does not match campaign sectors")
    else:
        explanations.append("Sector not set or no campaign sectors configured")
    points += sector_points

    # Geography match (0-10)
    geo_points = 0
    countries = [c.strip().lower() for c in settings.get("countries", []) if c.strip()]
    if countries and company.country:
        if company.country.lower() in countries:
            geo_points = 10
            explanations.append(f"Country '{company.country}' matches campaign countries")
        else:
            explanations.append(f"Country '{company.country}' not in campaign countries")
    else:
        explanations.append("Country not set or no campaign countries configured")
    points += geo_points

    # Employee range match (0-10)
    emp_points = 0
    c_min = settings.get("employee_min")
    c_max = settings.get("employee_max")
    if c_min is not None and c_max is not None:
        r_min = company.employee_min
        r_max = company.employee_max
        if r_min is not None and r_max is not None:
            if r_max >= c_min and r_min <= c_max:
                emp_points = 10
                explanations.append(f"Employee range {r_min}-{r_max} overlaps campaign range {c_min}-{c_max}")
            else:
                explanations.append(f"Employee range {r_min}-{r_max} does not overlap {c_min}-{c_max}")
        else:
            explanations.append("Company employee range incomplete")
    elif company.employee_min is not None or company.employee_max is not None:
        explanations.append("Company employee range incomplete")
    else:
        explanations.append("Employee range not set for company")
    points += emp_points

    # Domain presence (0-5)
    domain_points = 0
    if settings.get("require_domain", True):
        if company.website_domain:
            domain_points = 5
            explanations.append("Website domain present")
        else:
            explanations.append("No website domain (required by campaign)")
    points += domain_points

    return min(points, max_points), "; ".join(explanations), []


def calculate_evidence_quality(company: Company) -> tuple[int, str, list[str]]:
    """Calculate evidence quality score (0-25).
    
    Based on: source reliability, freshness, corroboration, factual support.
    """
    from .models import SourceRecord
    from .db import session_scope

    max_points = DEFAULT_WEIGHTS["evidence_quality"]
    points = 0
    explanations = []
    evidence_refs = []

    with session_scope() as db:
        sources = db.query(SourceRecord).filter(SourceRecord.company_id == company.id).all()

    if not sources:
        return 0, "No source records found", []

    # Count sources by type and status
    discovery_sources = [s for s in sources if s.source_type == "discovery"]
    enrichment_sources = [s for s in sources if s.source_type == "enrichment"]
    success_sources = [s for s in sources if s.status == "success_with_results"]

    # Source diversity (0-10)
    source_types = set(s.provider for s in success_sources)
    diversity_points = min(len(source_types) * 2, 10)
    points += diversity_points
    if diversity_points > 0:
        explanations.append(f"Evidence from {len(source_types)} distinct providers")

    # Freshness (0-8)
    freshness_points = 0
    now = datetime.now(timezone.utc)
    for source in success_sources:
        if source.retrieved_at:
            retrieved = source.retrieved_at
            if retrieved.tzinfo is None:
                # SQLite stores tz-aware datetimes as naive UTC
                retrieved = retrieved.replace(tzinfo=timezone.utc)
            age_days = (now - retrieved).days
            if age_days <= 30:
                freshness_points = max(freshness_points, 8)
            elif age_days <= 90:
                freshness_points = max(freshness_points, 5)
            elif age_days <= 365:
                freshness_points = max(freshness_points, 2)
    points += freshness_points
    if freshness_points > 0:
        explanations.append(f"Fresh evidence (most recent within 30 days)")

    # Corroboration (0-7)
    corr_points = 0
    # Count domains with multiple sources
    domain_sources = {}
    for source in success_sources:
        if source.company_id:
            domain_sources.setdefault(source.company_id, 0)
            domain_sources[source.company_id] += 1
    multi_source_companies = sum(1 for count in domain_sources.values() if count >= 2)
    if multi_source_companies > 0:
        corr_points = min(multi_source_companies * 2, 7)
        points += corr_points
        explanations.append(f"{multi_source_companies} companies corroborated by multiple sources")

    return min(points, max_points), "; ".join(explanations), []


def calculate_business_relevance(company: Company) -> tuple[int, str, list[str]]:
    """Calculate business relevance score (0-20).
    
    Based on: relevant news, hiring signals, funding, business signals.
    """
    from .models import SourceRecord
    from .db import session_scope

    max_points = DEFAULT_WEIGHTS["business_relevance"]
    points = 0
    explanations = []
    evidence_refs = []

    with session_scope() as db:
        sources = db.query(SourceRecord).filter(SourceRecord.company_id == company.id).all()

    enrichment_sources = [s for s in sources if s.source_type == "enrichment"]
    success_sources = [s for s in enrichment_sources if s.status == "success_with_results"]

    if not success_sources:
        return 0, "No enrichment evidence available", []

    # News signals (0-8)
    news_sources = [s for s in success_sources if s.source_type == "enrichment" and s.provider == "gnews"]
    if news_sources:
        points += min(len(news_sources) * 2, 8)
        explanations.append(f"{len(news_sources)} recent news articles found")

    # Hiring signals (0-7)
    job_sources = [s for s in success_sources if s.source_type == "enrichment" and s.provider == "greenhouse"]
    if job_sources:
        points += min(len(job_sources) * 2, 7)
        explanations.append(f"Hiring signals from {len(job_sources)} job postings")

    # SEC/funding signals (0-5)
    sec_sources = [s for s in success_sources if s.source_type == "enrichment" and s.provider == "sec"]
    if sec_sources:
        points += min(len(sec_sources) * 2, 5)
        explanations.append(f"SEC filings found ({len(sec_sources)} filings)")

    # Website enrichment (0-5)
    web_sources = [s for s in success_sources if s.source_type == "enrichment" and s.provider == "direct_fetch"]
    if web_sources:
        points += min(len(web_sources) * 2, 5)
        explanations.append("Website enrichment successful")

    return min(points, max_points), "; ".join(explanations), []


def calculate_contactability(company: Company) -> tuple[int, str, list[str]]:
    """Calculate contactability score (0-15).
    
    Based on: availability of legitimate, relevant professional contact route.
    """
    max_points = DEFAULT_WEIGHTS["contactability"]
    points = 0
    explanations = []

    # Website domain (0-5)
    if company.website_domain:
        points += 5
        explanations.append("Website domain available for contact research")

    # Email/contact info from enrichment (0-5)
    # This would come from enrichment sources - placeholder for now
    # In real implementation, would check for extracted emails, LinkedIn profiles, etc.
    explanations.append("Contactability assessment pending enrichment data")

    # Size-appropriate contactability (0-5)
    if company.employee_min is not None:
        if 20 <= company.employee_min <= 500:
            points += 5
            explanations.append("Company size suitable for direct outreach")
        elif company.employee_min > 500:
            points += 3
            explanations.append("Large company - may require different approach")
        else:
            points += 5
            explanations.append("Company size suitable for direct outreach")

    return min(points, max_points), "; ".join(explanations), []


def check_hard_exclusions(company: Company, campaign: 'Campaign') -> list[str]:
    """Check for hard exclusions that override scoring.
    
    Returns list of exclusion reasons (empty if none).
    """
    exclusions = []

    settings = campaign.settings if campaign else {}
    exclusions_list = settings.get("exclusions", [])

    # Check exclusion list (domains, names)
    for exclusion in exclusions_list:
        if exclusion.lower() in company.canonical_name.lower():
            return [f"Matches exclusion rule: {exclusion}"]
        if company.website_domain and exclusion.lower() in company.website_domain.lower():
            return [f"Domain matches exclusion rule: {exclusion}"]

    # Check do-not-contact / suppression list
    # In real implementation, would check against DNC/suppression database
    # For now, just return empty

    return []


def calculate_score(company: Company, campaign: 'Campaign') -> ScoreResult:
    """Main scoring function - calculates complete score result."""
    now = datetime.now(timezone.utc)
    all_refs = []

    # Check hard exclusions first
    hard_exclusions = check_hard_exclusions(company, campaign)
    if hard_exclusions:
        return ScoreResult(
            total_score=0,
            factors=[],
            confidence=0,
            qualification_status="rejected",
            qualification_reason="; ".join(hard_exclusions),
            hard_exclusions=hard_exclusions,
            requires_human_review=True,
            scored_at=datetime.now(timezone.utc),
        )

    # Calculate each factor
    fit_points, fit_exp, fit_refs = calculate_company_fit(company, campaign)
    all_refs.extend(fit_refs)

    evidence_points, evidence_exp, ev_refs = calculate_evidence_quality(company)
    all_refs.extend(ev_refs)

    relevance_points, relevance_exp, rel_refs = calculate_business_relevance(company)
    all_refs.extend(rel_refs)

    contact_points, contact_exp, contact_refs = calculate_contactability(company)
    all_refs.extend(contact_refs)

    factors = [
        ScoreFactor("Company Fit", DEFAULT_WEIGHTS["company_fit"], fit_points, fit_exp, fit_refs),
        ScoreFactor("Evidence Quality", DEFAULT_WEIGHTS["evidence_quality"], evidence_points, evidence_exp, ev_refs),
        ScoreFactor("Business Relevance", DEFAULT_WEIGHTS["business_relevance"], relevance_points, relevance_exp, rel_refs),
        ScoreFactor("Contactability", DEFAULT_WEIGHTS["contactability"], contact_points, contact_exp, contact_refs),
    ]

    total_score = sum(f.earned_points for f in factors)

    # Calculate confidence (separate from fit score)
    # Based on evidence quality and completeness
    confidence = min(evidence_points * 4, 100)  # Scale evidence quality to 0-100

    # Determine qualification status
    if total_score >= 75:
        qual_status = "qualified"
        qual_reason = None
    elif total_score >= 50:
        qual_status = "needs_review"
        qual_reason = "Score in review range (50-74)"
    else:
        qual_status = "rejected"
        qual_reason = "Score below threshold (0-49)"

    # Check if human review required
    requires_review = False
    if total_score < 75:
        requires_review = True
    # Also check for unknown/missing critical evidence
    # (This would check for missing critical fields)

    return ScoreResult(
        total_score=total_score,
        factors=factors,
        confidence=confidence,
        qualification_status=qual_status,
        qualification_reason=qual_reason,
        hard_exclusions=[],
        requires_human_review=requires_review,
        scored_at=datetime.now(timezone.utc),
    )


# Convenience function for API/integration
def score_company(company: Company, campaign: 'Campaign') -> ScoreResult:
    """Score a company and return full result."""
    return calculate_score(company, campaign)