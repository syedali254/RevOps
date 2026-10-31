"""Groq-powered draft agent for generating personalized outreach drafts."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..ai.groq_client import get_groq_service
from ..ai.structured_output import OutreachDraft, ChannelType, ConfidenceLevel
from .prompts import DRAFT_SYSTEM_PROMPT, DRAFT_USER_PROMPT_TEMPLATE, format_research_for_draft


class DraftAgent:
    """AI agent for generating personalized outreach drafts."""

    def __init__(self, groq_service=None):
        self.groq = groq_service or get_groq_service()

    async def generate_draft(
        self,
        channel: ChannelType,
        company_name: str,
        website_domain: Optional[str],
        research_profile: dict,
        value_prop: str = "We help B2B technology companies scale their outbound pipeline with evidence-based targeting.",
        campaign_goal: str = "Book a 15-minute discovery call",
        recipient_name: Optional[str] = None,
        recipient_title: Optional[str] = None,
    ) -> OutreachDraft:
        """Generate a personalized outreach draft for a specific channel."""
        
        # Format research profile for prompt
        research_text = self._format_research_for_prompt(research_profile)
        
        # Prepare prompt
        user_prompt = DRAFT_USER_PROMPT_TEMPLATE.format(
            channel=channel.value,
            recipient_name=recipient_name or "Decision Maker",
            recipient_title=recipient_title or "Decision Maker",
            company_name=company_name,
            research_profile_json=research_text,
            value_prop=value_prop,
            campaign_goal=campaign_goal,
        )
        
        messages = [
            {"role": "system", "content": DRAFT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        
        # Generate draft using structured output
        draft = await self.groq.structured_completion(
            messages=messages,
            response_model=OutreachDraft,
            temperature=0.2,  # Slightly higher for creativity
            max_tokens=2048,
        )
        
        # Post-process and validate
        draft = self._post_process_draft(draft, channel, research_profile)
        
        return draft

    def _format_research_for_prompt(self, profile: dict) -> str:
        """Format research profile for draft generation prompt."""
        if not profile:
            return "No research profile available."
        
        parts = []
        
        if profile.get("company_summary"):
            parts.append(f"COMPANY SUMMARY: {profile['company_summary']}")
        
        if profile.get("hiring_signals"):
            parts.append(f"HIRING SIGNALS ({len(profile['hiring_signals'])}):")
            for s in profile["hiring_signals"][:3]:
                parts.append(f"  - {s.get('claim', '')} (confidence: {s.get('confidence', 'low')})")
                if s.get("job_titles"):
                    parts.append(f"    Titles: {', '.join(s['job_titles'][:5])}")
                if s.get("technologies"):
                    parts.append(f"    Technologies: {', '.join(s['technologies'][:5])}")
        
        if profile.get("news_signals"):
            parts.append(f"NEWS/FUNDING SIGNALS ({len(profile['news_signals'])}):")
            for s in profile["news_signals"][:3]:
                parts.append(f"  - {s.get('title', s.get('claim', ''))} ({s.get('publisher', '')})")
                if s.get("description"):
                    parts.append(f"    {s['description'][:200]}...")
        
        if profile.get("tech_signals"):
            parts.append(f"TECH SIGNALS ({len(profile['tech_signals'])}):")
            for s in profile["tech_signals"][:3]:
                if s.get("technologies"):
                    parts.append(f"  - Technologies: {', '.join(s['technologies'][:10])}")
        
        if profile.get("decision_makers"):
            parts.append(f"DECISION MAKERS ({len(profile['decision_makers'])}):")
            for dm in profile["decision_makers"][:3]:
                parts.append(f"  - {dm.get('name', 'Unknown')}, {dm.get('title', 'Unknown Title')} (confidence: {dm.get('confidence', 'low')})")
        
        if profile.get("opening"):
            opening = profile["opening"]
            parts.append(f"SUGGESTED OPENING: {opening.get('text', '')}")
            parts.append(f"  Fallback used: {opening.get('fallback_used', False)}")
            parts.append(f"  Type: {opening.get('personalization_type', 'unknown')}")
        
        if profile.get("unknowns"):
            parts.append(f"UNKNOWNS: {'; '.join(profile['unknowns'][:5])}")
        
        if profile.get("limitations"):
            parts.append(f"LIMITATIONS: {'; '.join(profile['limitations'][:3])}")
        
        return "\n".join(parts)

    def _post_process_draft(self, draft: OutreachDraft, channel: ChannelType, research_profile: dict) -> OutreachDraft:
        """Post-process and validate the draft."""
        
        # Ensure channel matches
        draft.channel = channel
        
        # Validate evidence references exist in research
        # (In production, would cross-reference with actual evidence)
        
        # Add channel-specific defaults if missing
        if channel == ChannelType.EMAIL and not draft.subject:
            draft.subject = f"Quick question about {research_profile.get('company_name', 'your company')}"
        
        if channel == ChannelType.EMAIL and "opt-out" not in draft.body.lower() and "unsubscribe" not in draft.body.lower():
            draft.body += "\n\n---\nIf this isn't relevant, just let me know and I'll stop reaching out."
        
        # Ensure confidence matches personalization
        has_personalization = bool(draft.recipient_name and draft.recipient_title and 
                                   draft.recipient_name != "Decision Maker")
        if not has_personalization and draft.confidence == ConfidenceLevel.HIGH:
            draft.confidence = ConfidenceLevel.MEDIUM
            draft.fallback_used = True
        
        # Ensure personalization type is set
        if not draft.fallback_used and has_personalization:
            draft.fallback_used = False
        elif not has_personalization:
            draft.fallback_used = True
        
        return draft

    async def generate_multi_channel_drafts(
        self,
        company_name: str,
        website_domain: Optional[str],
        research_profile: dict,
        channels: list[ChannelType] = None,
        value_prop: str = "",
        campaign_goal: str = "",
    ) -> list[OutreachDraft]:
        """Generate drafts for multiple channels."""
        if channels is None:
            channels = [ChannelType.EMAIL, ChannelType.LINKEDIN]
        
        drafts = []
        for channel in channels:
            draft = await self.generate_draft(
                channel=channel,
                company_name=company_name,
                website_domain=website_domain,
                research_profile=research_profile,
                value_prop=value_prop,
                campaign_goal=campaign_goal,
            )
            drafts.append(draft)
        
        return drafts


class DraftAgentSync:
    """Synchronous wrapper for DraftAgent for use in LangGraph nodes."""
    
    def __init__(self):
        self.agent = DraftAgent()
    
    def generate_draft_sync(self, *args, **kwargs) -> OutreachDraft:
        """Synchronous wrapper for use in LangGraph."""
        return asyncio.run(self.agent.generate_draft(*args, **kwargs))
    
    def generate_multi_channel_drafts_sync(self, *args, **kwargs) -> list[OutreachDraft]:
        return asyncio.run(self.agent.generate_multi_channel_drafts(*args, **kwargs))


# Convenience functions
def create_draft_agent() -> DraftAgent:
    return DraftAgent()


def create_draft_agent_sync() -> DraftAgentSync:
    return DraftAgentSync()