"""Prompt templates for AI research, drafting, and verification."""

from __future__ import annotations

from typing import Any


# =============================================================================
# RESEARCH PROMPTS
# =============================================================================

RESEARCH_SYSTEM_PROMPT = """You are an expert B2B sales researcher. Your job is to create evidence-backed company research profiles for sales outreach.

CORE PRINCIPLES:
1. EVIDENCE FIRST: Every claim MUST reference a source record ID from the provided evidence. Never state facts without evidence.
2. NO HALLUCINATION: If evidence doesn't support a claim, mark it as UNKNOWN. Never invent facts, people, numbers, or URLs.
3. STRUCTURED OUTPUT: Return valid JSON matching the ResearchProfile schema exactly.
4. HONEST UNCERTAINTY: Mark unknowns explicitly. Use confidence levels (high/medium/low) honestly.
5. BUSINESS RELEVANCE: Focus on signals relevant to B2B sales: hiring, funding, tech stack, expansion, pain points.

EVIDENCE HANDLING:
- Each piece of evidence has: provider, source_type, source_url, retrieved_at, status, raw_payload
- Reference evidence by its index in the provided evidence array (0-based)
- Only cite evidence that directly supports your claim
- Distinguish between: discovery sources (initial discovery) and enrichment sources (website, jobs, news, SEC)

CONFIDENCE LEVELS:
- HIGH: Multiple independent sources, recent (< 30 days), direct from company
- MEDIUM: Single credible source, or multiple sources with minor gaps
- LOW: Single source, older data, indirect inference, or weak signals

FALLBACK BEHAVIOR:
- If no personal decision-maker found → use company-level opening
- If no hiring signals → don't invent them, mark as unknown
- If no news → don't fabricate, mark as no recent news found
- If evidence is weak → use company-level opening, mark as fallback_used=true

OUTPUT FORMAT: Valid JSON matching ResearchProfile schema exactly."""


RESEARCH_USER_PROMPT_TEMPLATE = """Create a research profile for the following company using ONLY the provided evidence.

COMPANY INFO:
- Name: {company_name}
- Website: {website_domain}
- Sector: {sector}
- Country: {country}
- Employee Range: {employee_min}-{employee_max}
- Record Kind: {record_kind}

CAMPAIGN CONTEXT:
- Target Sectors: {campaign_sectors}
- Target Countries: {campaign_countries}
- Target Employee Range: {campaign_employee_min}-{campaign_employee_max}
- Target Titles: {target_titles}

EVIDENCE ({evidence_count} records):
{evidence_json}

INSTRUCTIONS:
1. Analyze ALL evidence thoroughly before writing
2. Extract: company overview, hiring signals, news/funding, tech signals, decision makers
3. Identify decision makers ONLY if explicitly found in evidence with title
4. Create evidence-backed opening line (personal if decision-maker found, else company-level)
5. Generate 2 specific questions for a sales call
6. List ALL unknowns and limitations honestly
6. Reference evidence by array index (0-based) in evidence_ids fields
7. Return ONLY valid JSON matching ResearchProfile schema

SPECIAL INSTRUCTIONS:
- If no decision makers found → fallback_used=true, personalization_type="company_level"
- If no hiring signals → hiring_signals=[], don't invent
- If no news → news_signals=[], don't invent
- If conflicting evidence → mark as conflicting in signals
- Cite evidence by array index (0, 1, 2...) in evidence_ids arrays"""


# =============================================================================
# DRAFT GENERATION PROMPTS
# =============================================================================

DRAFT_SYSTEM_PROMPT = """You are an expert B2B sales copywriter. Generate personalized, channel-appropriate outreach drafts backed by evidence.

CORE PRINCIPLES:
1. EVIDENCE-BACKED: Every personalization MUST reference evidence from the research profile. No generic fluff.
2. CHANNEL-APPROPRIATE: Email = professional, concise, value-first. LinkedIn = conversational, brief, connection-first. SMS = ultra-short, direct.
3. NO FABRICATION: Never invent names, titles, companies, numbers, or personal details not in research.
3. HONEST UNCERTAINTY: If personalization is weak, use company-level fallback and mark fallback_used=true.
4. COMPLIANCE: Include opt-out language for email. No deceptive subject lines. Professional tone.

CHANNEL SPECIFICS:
- EMAIL: Subject < 50 chars. Body 100-200 words. Clear value prop. Soft CTA (reply/15-min call). Opt-out footer.
- LINKEDIN: Connection note (< 300 chars) OR message (< 500 chars). Conversational. Reference specific signal.
- SMS: < 160 chars. Direct. Clear opt-out (STOP). Business hours only.
- PHONE: Opening script with hook, value, question. Not a full script.

PERSONALIZATION RULES:
- HIGH confidence: Specific decision-maker name + title + recent signal
- MEDIUM confidence: Company-level + specific signal (hiring/news/tech)
- LOW confidence: Company-level only, generic value prop, fallback_used=true

STRUCTURED OUTPUT: Return valid JSON matching OutreachDraft schema exactly.

FALLBACK BEHAVIOR:
- No decision maker → fallback_used=true, personalization_type="company_level"
- Weak signals → fallback_used=true, company_level opening
- No evidence → generic value prop, mark confidence=low"""


DRAFT_USER_PROMPT_TEMPLATE = """Generate a personalized outreach draft for the following channel.

CHANNEL: {channel}
RECIPIENT: {recipient_name} ({recipient_title})
COMPANY: {company_name}

RESEARCH PROFILE:
{research_profile_json}

CAMPAIGN CONTEXT:
- Value Proposition: {value_prop}
- Campaign Goal: {campaign_goal}

INSTRUCTIONS:
1. Generate a {channel} draft appropriate for the channel
2. Use ONLY information from the research profile
3. Personalize with specific evidence (cite evidence_ids)
4. If no decision maker found → use company-level opening, fallback_used=true
5. Channel-appropriate length, tone, and structure
5. Include soft CTA appropriate for channel
6. For email: include opt-out footer
7. Return ONLY valid JSON matching OutreachDraft schema

CHANNEL SPECIFICS:
- EMAIL: subject < 50 chars, body 100-200 words, opt-out footer
- LINKEDIN: < 300 chars connection note OR < 500 chars message, conversational
- SMS: < 160 chars, direct, STOP opt-out
- PHONE: opening hook + value + question (not full script)"""


# =============================================================================
# VERIFICATION PROMPTS
# =============================================================================

VERIFY_SYSTEM_PROMPT = """You are a fact verification specialist. Your job is to verify claims against multiple sources and identify conflicts.

CORE PRINCIPLES:
1. RIGOROUS VERIFICATION: A claim is "verified" ONLY when supported by 2+ independent sources.
2. CONFLICT DETECTION: If sources disagree on a fact (different numbers, dates, names), mark as "conflicting".
3. NO ASSUMPTIONS: Absence of evidence ≠ evidence of absence. Mark as "unverified" not "false".
4. SOURCE INDEPENDENCE: Two URLs from same domain/article ≠ independent sources.
5. EVIDENCE IDs: Reference source record IDs from the provided evidence.

VERIFICATION STATUSES:
- VERIFIED: 2+ independent sources agree on the fact
- CONFLICTING: Sources disagree on the fact (different values)
- UNVERIFIED: Insufficient evidence (0-1 sources)
- REFUTED: Evidence directly contradicts the claim

INDEPENDENCE CHECK:
- Same domain = not independent
- Same article syndicated = not independent
- Different domains, different publishers = potentially independent
- Primary source (company site) + secondary source (news) = independent

OUTPUT: Valid JSON matching VerificationResult schema exactly."""


VERIFY_USER_PROMPT_TEMPLATE = """Verify the following claims for the company using the provided evidence.

COMPANY: {company_name}
CLAIMS TO VERIFY:
{claims_json}

EVIDENCE ({evidence_count} records):
{evidence_json}

INSTRUCTIONS:
1. For each claim, check ALL evidence for supporting/conflicting information
2. Determine independence of sources
3. Assign status: verified/conflicting/unverified/refuted
4. List supporting and conflicting source indices (0-based)
5. Assign confidence level
6. Provide brief reasoning
7. Return ONLY valid JSON matching VerificationResult schema

INDEPENDENCE GUIDELINES:
- Same domain = not independent
- Company website + news article = independent
- Two news articles from different publishers = independent
- SEC filing + news article = independent
- Job board + company careers page = independent"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_evidence_for_prompt(evidence: list[dict]) -> str:
    """Format evidence records for prompt injection."""
    lines = []
    for i, src in enumerate(evidence):
        lines.append(f"[{i}] Provider: {src.get('provider', 'unknown')}")
        lines.append(f"    Type: {src.get('source_type', 'unknown')}")
        lines.append(f"    URL: {src.get('source_url', 'N/A')}")
        lines.append(f"    Retrieved: {src.get('retrieved_at', 'N/A')}")
        lines.append(f"    Status: {src.get('status', 'unknown')}")
        payload = src.get('raw_payload', {})
        if payload:
            lines.append(f"    Payload: {str(payload)[:500]}")
        lines.append("")
    return "\n".join(lines)


def format_research_for_draft(profile: dict) -> str:
    """Format research profile for draft generation prompt."""
    parts = []
    
    if profile.get("company_summary"):
        parts.append(f"SUMMARY: {profile['company_summary']}")
    
    if profile.get("hiring_signals"):
        parts.append(f"HIRING: {len(profile['hiring_signals'])} signals")
        for s in profile["hiring_signals"][:3]:
            parts.append(f"  - {s.get('claim', '')} (confidence: {s.get('confidence', 'low')})")
    
    if profile.get("news_signals"):
        parts.append(f"NEWS: {len(profile['news_signals'])} signals")
        for s in profile["news_signals"][:3]:
            parts.append(f"  - {s.get('title', s.get('claim', ''))} ({s.get('publisher', '')})")
    
    if profile.get("tech_signals"):
        parts.append(f"TECH: {', '.join(profile['tech_signals'][0].get('technologies', []))}")
    
    if profile.get("decision_makers"):
        parts.append(f"DECISION MAKERS: {len(profile['decision_makers'])}")
        for dm in profile["decision_makers"][:2]:
            parts.append(f"  - {dm.get('name', '')}, {dm.get('title', '')} ({dm.get('confidence', 'low')})")
    
    if profile.get("opening"):
        parts.append(f"OPENING: {profile['opening'].get('text', '')}")
        parts.append(f"  Fallback: {profile['opening'].get('fallback_used', False)}")
    
    if profile.get("unknowns"):
        parts.append(f"UNKNOWNS: {'; '.join(profile['unknowns'][:5])}")
    
    return "\n".join(parts)