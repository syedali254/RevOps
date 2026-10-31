"""Groq-powered research agent with tool-calling for evidence-backed research."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from ..ai.groq_client import get_groq_service
from ..ai.structured_output import ResearchProfile, Signal, HiringSignal, NewsSignal, TechSignal, DecisionMaker, OpeningDraft
from .prompts import RESEARCH_SYSTEM_PROMPT, RESEARCH_USER_PROMPT_TEMPLATE, format_evidence_for_prompt


class ResearchAgent:
    """AI agent for generating evidence-backed company research profiles."""

    def __init__(self, groq_service=None):
        self.groq = groq_service or get_groq_service()

    async def generate_research(
        self,
        company_name: str,
        website_domain: Optional[str],
        sector: Optional[str],
        country: Optional[str],
        employee_min: Optional[int],
        employee_max: Optional[int],
        record_kind: str,
        campaign_sectors: list[str],
        campaign_countries: list[str],
        campaign_employee_min: Optional[int],
        campaign_employee_max: Optional[int],
        target_titles: list[str],
        evidence: list[dict],
    ) -> ResearchProfile:
        """Generate a complete research profile from evidence."""
        
        # Format evidence for prompt
        evidence_text = self._format_evidence(evidence)
        evidence_count = len(evidence)
        
        # Prepare prompt
        user_prompt = RESEARCH_USER_PROMPT_TEMPLATE.format(
            company_name=company_name,
            website_domain=website_domain or "N/A",
            sector=sector or "N/A",
            country=country or "N/A",
            employee_min=employee_min or "N/A",
            employee_max=employee_max or "N/A",
            record_kind=record_kind,
            campaign_sectors=", ".join(campaign_sectors) if campaign_sectors else "N/A",
            campaign_countries=", ".join(campaign_countries) if campaign_countries else "N/A",
            campaign_employee_min=campaign_employee_min or "N/A",
            campaign_employee_max=campaign_employee_max or "N/A",
            target_titles=", ".join(target_titles) if target_titles else "N/A",
            evidence_count=evidence_count,
            evidence_json=evidence_text,
        )
        
        messages = [
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        # Generate research profile using structured output
        profile = await self.groq.structured_completion(
            messages=[
                {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_model=ResearchProfile,
            temperature=0.1,
            max_tokens=4096,
        )
        
        # Post-process: validate evidence references
        profile = self._validate_evidence_refs(profile, evidence)
        
        # Add metadata
        profile.model_version = "llama-3.1-70b-versatile"
        profile.prompt_version = "1.0"
        
        return profile

    def _format_evidence(self, evidence: list[dict]) -> str:
        """Format evidence for prompt injection."""
        if not evidence:
            return "No evidence available."
        
        lines = []
        for i, src in enumerate(evidence):
            lines.append(f"[{i}] Provider: {src.get('provider', 'unknown')}")
            lines.append(f"    Type: {src.get('source_type', 'unknown')}")
            lines.append(f"    URL: {src.get('source_url', 'N/A')}")
            lines.append(f"    Retrieved: {src.get('retrieved_at', 'N/A')}")
            lines.append(f"    Status: {src.get('status', 'unknown')}")
            payload = src.get('raw_payload', {})
            if payload:
                # Truncate payload for prompt size
                payload_str = str(payload)[:800]
                lines.append(f"    Payload: {payload_str}")
            lines.append("")
        return "\n".join(lines)

    def _validate_evidence_refs(self, profile: ResearchProfile, evidence: list[dict]) -> ResearchProfile:
        """Validate that all evidence_ids reference valid evidence indices."""
        max_index = len(evidence) - 1
        
        def validate_refs(refs: list[str]) -> list[str]:
            valid = []
            for ref in refs:
                try:
                    idx = int(ref)
                    if 0 <= idx <= max_index:
                        valid.append(ref)
                except (ValueError, TypeError):
                    pass
            return valid
        
        # Validate all evidence reference fields
        profile.evidence_ids = validate_refs(profile.evidence_ids)
        
        for signal in profile.signals:
            signal.evidence_ids = validate_refs(signal.evidence_ids)
        
        for signal in profile.hiring_signals:
            signal.evidence_ids = validate_refs(signal.evidence_ids)
        
        for signal in profile.news_signals:
            signal.evidence_ids = validate_refs(signal.evidence_ids)
        
        for signal in profile.tech_signals:
            signal.evidence_ids = validate_refs(signal.evidence_ids)
        
        for dm in profile.decision_makers:
            dm.evidence_ids = validate_refs(dm.evidence_ids)
        
        profile.opening.evidence_ids = validate_refs(profile.opening.evidence_ids)
        
        return profile

    async def extract_signals(
        self,
        evidence: list[dict],
        company_name: str,
    ) -> dict:
        """Extract structured signals from evidence using AI."""
        # This can be used for incremental signal extraction
        # For now, the main generate_research handles this
        pass


class ResearchAgentSync:
    """Synchronous wrapper for ResearchAgent for use in LangGraph nodes."""
    
    def __init__(self):
        self.agent = ResearchAgent()
    
    def generate_research_sync(self, *args, **kwargs) -> ResearchProfile:
        """Synchronous wrapper for use in LangGraph."""
        return asyncio.run(self.agent.generate_research(*args, **kwargs))


# Convenience function for LangGraph nodes
def create_research_agent() -> ResearchAgent:
    """Create a ResearchAgent instance with default Groq service."""
    return ResearchAgent()


def create_research_agent_sync() -> ResearchAgentSync:
    """Create a synchronous ResearchAgent wrapper."""
    return ResearchAgentSync()