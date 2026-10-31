"""Groq-powered verification agent for fact checking and corroboration."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..ai.groq_client import get_groq_service
from ..ai.structured_output import (
    VerificationResult, FactVerification, ConfidenceLevel,
    Signal, HiringSignal, NewsSignal
)
from .prompts import VERIFY_SYSTEM_PROMPT, VERIFY_USER_PROMPT_TEMPLATE, format_evidence_for_prompt


class VerifyAgent:
    """AI agent for verifying facts across multiple sources."""

    def __init__(self, groq_service=None):
        self.groq = groq_service or get_groq_service()

    async def verify_claims(
        self,
        company_name: str,
        claims: list[str],
        evidence: list[dict],
    ) -> VerificationResult:
        """Verify multiple claims against evidence."""
        
        # Format evidence for prompt
        evidence_text = self._format_evidence(evidence)
        evidence_count = len(evidence)
        
        claims_json = json.dumps([{"claim": c} for c in claims], indent=2)
        
        # Prepare prompt
        user_prompt = VERIFY_USER_PROMPT_TEMPLATE.format(
            company_name=company_name,
            claims_json=claims_json,
            evidence_count=evidence_count,
            evidence_json=evidence_text,
        )
        
        messages = [
            {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        # Generate verification using structured output
        result = await self.groq.structured_completion(
            messages=messages,
            response_model=VerificationResult,
            temperature=0.0,  # Zero temperature for deterministic verification
            max_tokens=4096,
        )
        
        # Post-process: validate source references
        result = self._validate_source_refs(result, evidence)
        
        return result

    async def verify_single_claim(
        self,
        company_name: str,
        claim: str,
        evidence: list[dict],
    ) -> FactVerification:
        """Verify a single claim."""
        result = await self.verify_claims(company_name, [claim], evidence)
        return result.verifications[0] if result.verifications else FactVerification(
            claim=claim,
            status="unverified",
            confidence=ConfidenceLevel.LOW,
            reasoning="No verification performed",
        )

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
                payload_str = str(payload)[:800]
                lines.append(f"    Payload: {payload_str}")
            lines.append("")
        return "\n".join(lines)

    def _validate_source_refs(self, result: VerificationResult, evidence: list[dict]) -> VerificationResult:
        """Validate that all source references are valid indices."""
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
        
        for verification in result.verifications:
            verification.supporting_sources = validate_refs(verification.supporting_sources)
            verification.conflicting_sources = validate_refs(verification.conflicting_sources)
            verification.evidence_ids = validate_refs(verification.evidence_ids)
        
        return result

    async def verify_research_profile(
        self,
        company_name: str,
        profile: dict,
        evidence: list[dict],
    ) -> VerificationResult:
        """Verify all claims in a research profile."""
        
        # Extract claims from profile
        claims = []
        
        # Company summary claims
        if profile.get("company_summary"):
            claims.append(profile["company_summary"])
        
        # Hiring signal claims
        for signal in profile.get("hiring_signals", []):
            claims.append(signal.get("claim", ""))
        
        # News signal claims
        for signal in profile.get("news_signals", []):
            claims.append(signal.get("title", signal.get("claim", "")))
        
        # Tech signal claims
        for signal in profile.get("tech_signals", []):
            if signal.get("technologies"):
                claims.append(f"Uses technologies: {', '.join(signal['technologies'])}")
        
        # Decision maker claims
        for dm in profile.get("decision_makers", []):
            claims.append(f"{dm.get('name', '')} holds title {dm.get('title', '')} at {company_name}")
        
        # Filter empty claims
        claims = [c for c in claims if c.strip()]
        
        if not claims:
            return VerificationResult(
                company_id=0,
                verifications=[],
                overall_confidence=ConfidenceLevel.LOW,
                verified_count=0,
                conflicting_count=0,
                unverified_count=0,
                needs_human_review=False,
            )
        
        return await self.verify_claims(company_name, claims, evidence)


class VerifyAgentSync:
    """Synchronous wrapper for VerifyAgent for use in LangGraph nodes."""
    
    def __init__(self):
        self.agent = VerifyAgent()
    
    def verify_claims_sync(self, *args, **kwargs) -> VerificationResult:
        return asyncio.run(self.agent.verify_claims(*args, **kwargs))
    
    def verify_research_profile_sync(self, *args, **kwargs) -> VerificationResult:
        return asyncio.run(self.agent.verify_research_profile(*args, **kwargs))


# Convenience functions
def create_verify_agent() -> VerifyAgent:
    return VerifyAgent()


def create_verify_agent_sync() -> VerifyAgentSync:
    return VerifyAgentSync()