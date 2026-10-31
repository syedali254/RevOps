"""AI service package for Groq-powered research and drafting."""

from .groq_client import GroqService, get_groq_service
from .structured_output import (
    ResearchProfile,
    OutreachDraft,
    Signal,
    HiringSignal,
    NewsSignal,
    TechSignal,
    DecisionMaker,
    OpeningDraft,
)
from .prompts import (
    RESEARCH_SYSTEM_PROMPT,
    RESEARCH_USER_PROMPT_TEMPLATE,
    DRAFT_SYSTEM_PROMPT,
    DRAFT_USER_PROMPT_TEMPLATE,
    VERIFY_SYSTEM_PROMPT,
    VERIFY_USER_PROMPT_TEMPLATE,
)
from .research_agent import ResearchAgent, create_research_agent_sync
from .draft_agent import DraftAgent, create_draft_agent_sync
from .verify_agent import VerifyAgent, create_verify_agent_sync

__all__ = [
    "GroqService",
    "get_groq_service",
    "ResearchProfile",
    "OutreachDraft",
    "Signal",
    "HiringSignal",
    "NewsSignal",
    "TechSignal",
    "DecisionMaker",
    "OpeningDraft",
    "RESEARCH_SYSTEM_PROMPT",
    "RESEARCH_USER_PROMPT_TEMPLATE",
    "DRAFT_SYSTEM_PROMPT",
    "DRAFT_USER_PROMPT_TEMPLATE",
    "VERIFY_SYSTEM_PROMPT",
    "VERIFY_USER_PROMPT_TEMPLATE",
    "ResearchAgent",
    "create_research_agent_sync",
    "DraftAgent",
    "create_draft_agent_sync",
    "VerifyAgent",
    "create_verify_agent_sync",
]