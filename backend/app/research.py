"""Evidence-backed research brief generation.

Generates a company research brief from retrieved source records.
If no AI API key is configured, uses a deterministic template.
"""

from __future__ import annotations

import os
import json
from datetime import datetime, timezone
from typing import Any, Optional

from .models import Company, Campaign, SourceRecord
from .db import session_scope
from .ai import get_groq_service, create_research_agent_sync


def _collect_evidence(company: Company) -> dict[str, list[dict]]:
    """Collect and organize evidence from source records."""
    with session_scope() as db:
        sources = db.query(SourceRecord).filter(
            SourceRecord.company_id == company.id
        ).order_by(SourceRecord.retrieved_at.desc()).all()

    evidence = {
        "discovery": [],
        "enrichment": [],
        "by_provider": {},
        "by_type": {},
    }

    for src in sources:
        record = {
            "id": src.id,
            "provider": src.provider,
            "source_type": src.source_type,
            "source_url": src.source_url,
            "retrieved_at": src.retrieved_at.isoformat() if src.retrieved_at else None,
            "published_at": src.published_at.isoformat() if src.published_at else None,
            "status": src.status,
            "error_message": src.error_message,
        }
        try:
            record["raw_payload"] = json.loads(src.raw_payload_json) if src.raw_payload_json else {}
        except Exception:
            record["raw_payload"] = {}

        evidence["by_type"].setdefault(src.source_type, []).append(record)
        evidence["by_provider"].setdefault(src.provider, []).append(record)

        if src.source_type == "discovery":
            evidence["discovery"].append(record)
        elif src.source_type == "enrichment":
            evidence["enrichment"].append(record)

    return evidence


def _extract_company_overview(company: Company, evidence: dict) -> str:
    """Extract a company overview from evidence."""
    parts = [f"{company.canonical_name} is a company"]
    if company.sector:
        parts.append(f"operating in the {company.sector} sector")
    if company.country:
        parts.append(f"based in {company.country}")
    if company.employee_min and company.employee_max:
        parts.append(f"with {company.employee_min}-{company.employee_max} employees")
    elif company.employee_min:
        parts.append(f"with {company.employee_min}+ employees")

    # Try to get description from discovery sources
    for src in evidence.get("discovery", []):
        payload = src.get("raw_payload", {})
        if payload.get("snippet"):
            parts.append(f"According to {src['provider']}: {payload['snippet']}")
            break

    return ". ".join(parts) + "."


def _extract_hiring_signals(evidence: dict) -> list[dict]:
    """Extract hiring signals from enrichment sources."""
    signals = []
    for src in evidence.get("enrichment", []):
        if src.get("provider") in ("greenhouse", "remoteok"):
            payload = src.get("raw_payload", {})
            if payload.get("job_count", 0) > 0 or payload.get("positions"):
                signals.append({
                    "provider": src["provider"],
                    "job_count": payload.get("job_count", 0),
                    "positions": payload.get("positions", []),
                    "sample_job": payload.get("sample_job", ""),
                    "source_url": src.get("source_url"),
                    "retrieved_at": src.get("retrieved_at"),
                })
    return signals


def _extract_news_signals(evidence: dict) -> list[dict]:
    """Extract news/funding signals from enrichment sources."""
    signals = []
    for src in evidence.get("enrichment", []):
        if src.get("provider") in ("gnews", "sec"):
            payload = src.get("raw_payload", {})
            if src.get("provider") == "gnews" and payload.get("articles"):
                for article in payload["articles"][:5]:
                    signals.append({
                        "type": "news",
                        "title": article.get("title", ""),
                        "source": article.get("source", ""),
                        "url": article.get("url", ""),
                        "published_at": article.get("published_at", ""),
                        "description": article.get("description", "")[:300],
                    })
            elif src.get("provider") == "sec" and payload.get("filings"):
                for filing in payload["filings"][:5]:
                    signals.append({
                        "type": "sec_filing",
                        "form": filing.get("form", ""),
                        "filing_date": filing.get("filing_date", ""),
                        "description": filing.get("primary_doc_description", ""),
                        "url": filing.get("source_url", ""),
                    })
    return signals


def _extract_website_evidence(evidence: dict) -> list[dict]:
    """Extract website enrichment evidence."""
    signals = []
    for src in evidence.get("enrichment", []):
        if src.get("provider") == "direct_fetch":
            payload = src.get("raw_payload", {})
            if payload.get("fields"):
                for field in payload["fields"]:
                    signals.append({
                        "field": field.get("field_name", ""),
                        "value": field.get("value", ""),
                        "source_url": field.get("source_url", ""),
                        "snippet": field.get("snippet", ""),
                        "confidence": field.get("confidence", 0),
                    })
    return signals


def _generate_template_brief(company: Company, evidence: dict, campaign: Optional[Campaign]) -> str:
    """Generate a deterministic research brief from evidence (no AI required)."""
    lines = []

    # Header
    lines.append(f"# Research Brief: {company.canonical_name}")
    lines.append("")
    lines.append(f"**Campaign:** {campaign.name if campaign else 'N/A'}")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"**Company ID:** {company.id}")
    lines.append("")

    # Company Overview
    lines.append("## Company Overview")
    lines.append("")
    lines.append(_extract_company_overview(company, {"discovery": evidence.get("discovery", [])}))
    lines.append("")

    # Company Profile
    lines.append("## Company Profile")
    lines.append("")
    if company.website_domain:
        lines.append(f"- **Website:** {company.website_domain}")
    if company.country:
        lines.append(f"- **Country:** {company.country}")
    if company.sector:
        lines.append(f"- **Sector:** {company.sector}")
    if company.employee_min and company.employee_max:
        lines.append(f"- **Employees:** {company.employee_min}-{company.employee_max}")
    elif company.employee_min:
        lines.append(f"- **Employees:** {company.employee_min}+")
    lines.append("")

    # Discovery Sources
    discovery = evidence.get("discovery", [])
    if discovery:
        lines.append("## Discovery Sources")
        lines.append("")
        for src in discovery:
            lines.append(f"- **{src['provider']}** ({src['status']})")
            if src.get("source_url"):
                lines.append(f"  - Source: {src['source_url']}")
            payload = src.get("raw_payload", {})
            if payload.get("snippet"):
                lines.append(f"  - Snippet: {payload['snippet'][:200]}...")
            lines.append(f"  - Retrieved: {src.get('retrieved_at', 'N/A')}")
        lines.append("")

    # Enrichment Sources
    enrichment = evidence.get("enrichment", [])
    if enrichment:
        lines.append("## Enrichment Signals")
        lines.append("")

        # Hiring signals
        hiring = _extract_hiring_signals(evidence)
        if hiring:
            lines.append("### Hiring Signals")
            lines.append("")
            for h in hiring:
                lines.append(f"- **{h['provider']}**: {h['job_count']} job postings")
                if h.get("sample_job"):
                    lines.append(f"  - Example: {h['sample_job']}")
                if h.get("source_url"):
                    lines.append(f"  - Source: {h['source_url']}")
            lines.append("")

        # News signals
        news = _extract_news_signals(evidence)
        if news:
            lines.append("### News & Funding")
            lines.append("")
            for n in news[:10]:
                lines.append(f"- **{n['type'].title()}**: {n.get('title', n.get('form', 'Filing'))}")
                if n.get("source"):
                    lines.append(f"  - Source: {n['source']}")
                if n.get("url"):
                    lines.append(f"  - URL: {n['url']}")
                if n.get("published_at"):
                    lines.append(f"  - Published: {n['published_at']}")
                if n.get("description"):
                    lines.append(f"  - Description: {n['description'][:200]}...")
            lines.append("")

        # Website evidence
        web = _extract_website_evidence(evidence)
        if web:
            lines.append("### Website Evidence")
            lines.append("")
            for w in web[:10]:
                lines.append(f"- **{w['field']}**: {w['value'][:200]}")
                if w.get("source_url"):
                    lines.append(f"  - Source: {w['source_url']}")
            lines.append("")

    # Unknowns and Gaps
    lines.append("## Unknowns & Verification Gaps")
    lines.append("")
    all_sources = evidence.get("by_provider", {})
    if not all_sources:
        lines.append("- No source records available. All facts are unverified.")
    else:
        missing = []
        if not any(p in all_sources for p in ("gnews", "sec")):
            missing.append("Recent news/funding")
        if not any(p in all_sources for p in ("greenhouse", "remoteok")):
            missing.append("Hiring signals")
        if "direct_fetch" not in all_sources:
            missing.append("Website content extraction")
        if not company.website_domain:
            missing.append("Verified website domain")
        if not company.employee_min and not company.employee_max:
            missing.append("Employee count")
        if missing:
            lines.append("- Missing evidence for: " + ", ".join(missing))
        else:
            lines.append("- Key evidence categories are present")
    lines.append("")

    # Fit Assessment
    lines.append("## Campaign Fit Assessment")
    lines.append("")
    lines.append("*This section should be cross-referenced with the quantitative score breakdown.*")
    lines.append("")

    # Sources Summary
    lines.append("## All Sources")
    lines.append("")
    for provider, records in evidence.get("by_provider", {}).items():
        success = [r for r in records if r["status"] == "success_with_results"]
        lines.append(f"- **{provider}**: {len(records)} records ({len(success)} with results)")
    lines.append("")

    return "\n".join(lines)


def generate_research_brief(
    company: Company,
    campaign: Optional[Campaign] = None,
    ai_model: Optional[str] = None,
) -> str:
    """Generate a research brief for a company.

    Uses Groq AI when configured, otherwise deterministic template fallback.
    """
    evidence = _collect_evidence(company)

    # Check if AI should be used (Groq)
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    use_ai = bool(groq_api_key)

    if use_ai:
        try:
            return _generate_ai_brief(company, evidence, campaign)
        except Exception as e:
            # Fall back to template on any AI error
            pass

    # Deterministic template (always available)
    return _generate_template_brief(company, evidence, campaign)


def _generate_ai_brief(
    company: Company,
    evidence: dict,
    campaign: Optional[Campaign] = None,
) -> str:
    """Generate brief using Groq AI. Validates output against evidence."""
    
    # Prepare evidence for AI agent
    evidence_list = []
    for src in evidence.get("discovery", []) + evidence.get("enrichment", []):
        evidence_list.append({
            "id": src.get("id"),
            "provider": src.get("provider"),
            "source_type": src.get("source_type"),
            "source_url": src.get("source_url"),
            "retrieved_at": src.get("retrieved_at"),
            "published_at": src.get("published_at"),
            "status": src.get("status"),
            "error_message": src.get("error_message"),
            "raw_payload": src.get("raw_payload", {}),
        })

    # Prepare campaign settings
    campaign_settings = {}
    if campaign:
        campaign_settings = campaign.settings or {}

    # Create and run research agent
    agent = create_research_agent_sync()
    
    # Prepare campaign settings for agent
    sectors = campaign_settings.get("sectors", []) if campaign_settings else []
    countries = campaign_settings.get("countries", []) if campaign_settings else []
    employee_min = campaign_settings.get("employee_min") if campaign_settings else None
    employee_max = campaign_settings.get("employee_max") if campaign_settings else None
    target_titles = campaign_settings.get("target_titles", []) if campaign_settings else []

    profile = agent.generate_research_sync(
        company_name=company.canonical_name,
        website_domain=company.website_domain,
        sector=company.sector,
        country=company.country,
        employee_min=company.employee_min,
        employee_max=company.employee_max,
        record_kind=company.record_kind,
        campaign_sectors=sectors,
        campaign_countries=countries,
        campaign_employee_min=employee_min,
        campaign_employee_max=employee_max,
        target_titles=target_titles,
        evidence=evidence_list,
    )

    # Convert ResearchProfile to markdown brief
    return _profile_to_markdown(profile, company, campaign)


def generate_research_brief_for_company(
    company_id: int,
    campaign_id: Optional[int] = None,
) -> str:
    """Convenience function to generate brief from DB IDs."""
    with session_scope() as db:
        company = db.get(Company, company_id)
        if not company:
            raise ValueError(f"Company {company_id} not found")
        campaign = db.get(Campaign, campaign_id) if campaign_id else None

    return generate_research_brief(company, campaign)