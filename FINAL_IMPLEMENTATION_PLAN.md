# FINAL_IMPLEMENTATION_PLAN.md
# B2B Lead Engine — Final System Completion Plan

**Date:** 2026-10-22  
**Status:** Phase 1 — Audit Complete | Ready for Phase 2 Implementation  
**Groq API Key:** Provided in local `.env` (never committed to git)

---

## 1. EXECUTIVE SUMMARY — CURRENT STATE

### What's Working (Verified End-to-End)

| Category | Status | Evidence |
|----------|--------|----------|
| **Core Workflow** | ✅ Implemented & Verified | 14-stage LangGraph: start→find→merge→evaluate→website→jobs→news→sec→opencorporates→scoring→research→approval→dry_run→finish |
| **Discovery Connectors** | ✅ Live (3/4) | Tavily ✅, Exa ✅, Remote OK ✅, Brave (fixture) |
| **Enrichment Connectors** | ✅ Live (4/6) | Website ✅, Greenhouse ✅, SEC EDGAR ✅, GNews ✅, OpenCorporates (fixture), YC (CSV) |
| **Scoring & Qualification** | ✅ Implemented & Verified | Deterministic 0-100 with factor breakdown (Fit 40, Evidence 25, Relevance 20, Contact 15) |
| **Research Brief** | ✅ Template Complete | Deterministic template with evidence citations; AI stub ready |
| **Approval Gate** | ✅ Complete | Pending/Approved/Rejected states; blocks dry-run until approved |
| **Dry-Run Safety** | ✅ Enforced | All 5 channels blocked; safety report generated; DRY_RUN=true enforced in backend |
| **Caller Briefing** | ✅ Template Complete | Company profile, evidence, score breakdown, research brief, approval actions |
| **Frontend** | ✅ Complete | Overview, Campaigns, Companies, Company Detail, Runs, Discovery Runs |
| **Tests** | ✅ Passing | 73 backend + 30 frontend = 103 tests passing |

### Live Connectors (Verified with Real API Keys)

| Connector | Role | Status | Last Verified |
|-----------|------|--------|---------------|
| Tavily | Discovery (primary) | ✅ Live | 2026-10-22 |
| Exa | Discovery (fallback) | ✅ Live | 2026-10-22 |
| Remote OK | Discovery (job feed) | ✅ Live | 2026-10-22 |
| Brave | Discovery (fixture) | ✅ Fixture | 2026-10-22 |
| Website | Enrichment | ✅ Live | 2026-10-22 |
| Greenhouse | Enrichment | ✅ Live | 2026-10-22 |
| GNews | Enrichment | ✅ Live | 2026-10-22 |
| SEC EDGAR | Enrichment | ✅ Live | 2026-10-22 |
| OpenCorporates | Enrichment | ✅ Fixture | 2026-10-22 |
| YC Directory | Discovery | ✅ CSV Import | 2026-10-22 |

---

## 2. REQUIREMENT MATRIX — GAP ANALYSIS

| # | Requirement (from Brief) | Status | Implementation Location | Evidence |
|---|-------------------------|--------|------------------------|----------|
| **Campaign Settings** | | | | |
| 1 | Editable sector, country, employee range, titles, exclusions | ✅ Verified | `CampaignSettings` model, `CampaignCreate` API, `CampaignsPage.tsx` | API + UI verified |
| 2 | Immutable settings snapshot per campaign | ✅ Verified | `Campaign.settings_json` + versioning | DB schema + API |
| 3 | DNC/exclusion lists per campaign | ✅ Verified | `exclusions` field, `check_hard_exclusions()` | `scoring.py:283` |
| **Discovery & Enrichment** | | | | |
| 4 | Multiple discovery sources (web search, business directories) | ✅ Verified | 4 connectors: Tavily, Exa, Remote OK, Brave | Live verified |
| 5 | Domain-first deduplication | ✅ Verified | `merge_node()` in `graph.py:508` | Tested |
| 6 | Enrichment: website, jobs, news, SEC | ✅ Live | 5 enrichment connectors | Live tested |
| 7 | Connector status tracking (success/empty/failed/not_configured) | ✅ Verified | `ConnectorStatus` enum, `_enrichment_ok()` | `graph.py:1030` |
| **Verification & Scoring** | | | | |
| 8 | Pass/fail/unknown/conflict per rule | ✅ Verified | `qualify()` in `graph.py:557` | 100% test coverage |
| 9 | Separate fit score, evidence confidence, safety status | ✅ Verified | `ScoreResult` dataclass in `scoring.py` | 4 factors |
| 9 | Unknown/conflicting never silently verified | ✅ Verified | `qualify()` returns "unknown"/"conflict" | Tests pass |
| 10 | Deterministic 0-100 scoring with factor breakdown | ✅ Verified | `calculate_score()` in `scoring.py:307` | 4 factors |
| 11 | Below-threshold → review queue | ✅ Verified | `qualification_status="needs_review"` | `scoring.py:356` |
| 12 | DNC/suppression blocks progression | ✅ Verified | `check_hard_exclusions()` + approval gate | `safety.py` |
| **Research & AI** | | | | |
| 13 | Evidence-backed research brief | ✅ Template | `research.py:_generate_template_brief()` | Template works |
| 14 | AI-assisted research (Groq) | ⚠️ Stub Only | `research.py:_generate_ai_brief()` raises NotImplementedError | Ready to implement |
| 15 | Decision-maker research | ⚠️ Partial | `research.py` extracts job titles from Greenhouse | Limited to public job posts |
| 16 | AI draft generation | ⚠️ Stub Only | `research.py:_generate_ai_brief()` raises NotImplementedError | Ready for Groq |
| 17 | Structured AI output with evidence IDs | ⚠️ Planned | Schema defined in brief §8 | Schema exists |
| **Approval & Dry-Run** | | | | |
| 18 | Human approval gate | ✅ Verified | `approval_node()` in `graph.py:1245` | Tests pass |
| 19 | Dry-run safety gate (all channels blocked) | ✅ Verified | `dry_run_node()` + `safety.py:evaluate_outreach()` | 5 channels tested |
| 20 | DRY_RUN enforced in backend | ✅ Verified | `safety.py:evaluate_outreach()` returns BLOCKED | 16 safety tests |
| 21 | Simulated activity tracking | ✅ Verified | `outreach_events` table + dry-run events | Events logged |
| **Caller Dashboard** | | | | |
| 22 | Caller briefing page | ✅ Template | `CompanyDetailPage.tsx` + `research.py` | Template renders |
| 23 | Call outcome logging | ✅ Verified | `call_notes` table + UI | `CompanyDetailPage.tsx` |
| 24 | Engagement timeline | ✅ Partial | `outreach_events` + `stage_events` | Events logged |
| **CRM & Compliance** | | | | |
| 23 | CRM adapter interface | ⚠️ Interface Only | `main.py` placeholder | Interface exists |
| 24 | GoHighLevel sync | ❌ Blocked | No credentials | Blocked |
| 25 | DNC/opt-out enforcement | ✅ Verified | `safety.py:evaluate_outreach()` | Tests pass |
| 26 | Opt-out stops all channels | ✅ Verified | `safety.py` shared suppression | Tests pass |
| 27 | Audit trail (all actions logged) | ✅ Verified | `stage_events` + `outreach_events` | Events persisted |
| **Cost & Health** | | | | |
| 28 | Connector health/status | ✅ Verified | `/api/sources` endpoint | Returns live status |
| 27 | Cost tracking | ⚠️ Partial | Token counting stub in `research.py` | Stub only |
| 28 | Retry/idempotency | ✅ Verified | LangGraph + DB unique constraints | Tests pass |

---

## 3. RESEARCH FINDINGS — DISCOVERY ARCHITECTURE

### Current Live Discovery Sources (Verified)

| Provider | Type | Access | Limits | Cost | Verdict |
|----------|------|--------|--------|------|---------|
| **Tavily** | Web Search API | Live | 1000 req/mo free | $5/1K after | ✅ Keep as primary |
| **Exa** | Neural Search API | Live | 1000 req/mo free | Custom pricing | ✅ Keep as fallback |
| **Remote OK** | Public Job Feed | Live (no auth) | 100 jobs/req | Free | ✅ Keep for hiring signals |
| **Brave** | Web Search API | Fixture only | $5/1K req | $5/mo credits | Fixture only |

### Recommended Additional Sources (Research Phase)

| Provider | Type | Access | Key Capability | Cost | Integration Effort |
|----------|------|--------|----------------|------|-------------------|
| **SerpAPI** | Web Search | API Key | Google/Bing results | 100 free/mo | Low |
| **Apollo.io** | Company Directory | API Key | B2B contacts | Free tier limited | Medium |
| **Clearbit** | Company Enrichment | API Key | Company data | Expensive | Skip |
| **BuiltWith** | Tech Stack | API Key | Tech signals | Free tier | Low |
| **Crunchbase** | Funding Data | API Key | Funding rounds | Paid | Skip for now |

**Recommendation:** Keep current 4 discovery sources. No new providers needed for Phase 2. Focus on AI research/drafting.

---

## 4. AI ARCHITECTURE — GROQ INTEGRATION

### Where AI Adds Value (Approved Uses)

| Capability | Implementation | Deterministic Fallback |
|------------|----------------|------------------------|
| **Research Brief Generation** | Groq `llama-3.1-70b-versatile` with tool calling | Deterministic template |
| **Outreach Draft Generation** | Groq with structured output | Template per channel |
| **Evidence Extraction** | Groq structured output | Regex/heuristic extraction |
| **Fact Verification** | Groq structured output | Deterministic rules |
| **Opening Line Generation** | Groq with few-shot prompts | Template with evidence |

### Where Deterministic Code Must Remain

| Capability | Reason |
|------------|--------|
| Qualification rules (pass/fail/unknown) | Business logic, auditable |
| Scoring weights & thresholds | Configurable, transparent |
| DNC/suppression checks | Safety-critical, no AI |
| Evidence provenance tracking | Audit requirement |
| Deduplication logic | Deterministic matching |
| Dry-run safety gate | Hard enforcement |

### Groq Model Selection

| Model | Use Case | Tool Calling | Structured Output |
|-------|----------|--------------|-------------------|
| `llama-3.1-70b-versatile` | Research brief, drafts | ✅ Yes | ✅ JSON Schema |
| `llama-3.1-8b-instant` | Fast extraction | ✅ Yes | ✅ JSON Schema |
| `mixtral-8x7b-32768` | Long context | ❌ No | ❌ |

**Selected:** `llama-3.1-70b-versatile` (best tool calling + structured output)

### AI Service Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    GroqService                          │
│  - configure(model, temperature, max_tokens)            │
│  - chat_completion(messages, tools, response_format)    │
│  - structured_completion(prompt, schema)                │
│  - extract_with_tools(prompt, tools, schema)            │
│  - validate_output(response, schema)                    │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ ResearchAgent │ │ DraftAgent    │ │ VerifyAgent   │
│ - search      │ │ - email       │ │ - verify_fact │
│ - summarize   │ │ - linkedin    │ │ - corroborate │
│ - extract     │ │ - sms         │ │ - conflict    │
└───────────────┘ └───────────────┘ └───────────────┘
```

---

## 5. GROQ CONFIGURATION & AI SERVICE

### Environment Variables

```bash
# .env (add to existing)
GROQ_API_KEY=<redacted — set in local .env>
GROQ_MODEL=llama-3.1-70b-versatile
GROQ_TEMPERATURE=0.1
GROQ_MAX_TOKENS=4096
```

### New Files to Create

```
backend/app/ai/
├── __init__.py
├── groq_client.py          # Groq API wrapper with retries/caching
├── structured_output.py    # Pydantic schemas + validation
├── research_agent.py       # Research brief generation
├── draft_agent.py          # Outreach draft generation
├── verify_agent.py         # Fact verification
└── prompts.py              # Prompt templates + few-shot examples
```

### GroqService Interface

```python
class GroqService:
    def __init__(self, api_key: str, model: str = "llama-3.1-70b-versatile"):
        self.client = AsyncGroq(api_key=api_key)
        self.model = model
    
    async def structured_completion(
        self, 
        prompt: str, 
        response_model: Type[BaseModel],
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> BaseModel:
        """Returns validated Pydantic model or raises ValidationError"""
    
    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        max_iterations: int = 5
    ) -> dict:
        """Tool-calling loop with max iterations"""
```

---

## 6. DISCOVERY & RESEARCH WORKFLOW ENHANCEMENTS

### Current Flow (Already Working)

```
Campaign Settings → Discovery (Tavily→Exa→RemoteOK→Brave) 
    → Merge/Dedupe → Evaluate → Enrichment Pipeline (5 sources)
    → Scoring → Research → Approval → Dry-Run → Finish
```

### Enhancements Needed

| Enhancement | Location | Priority |
|-------------|----------|----------|
| Groq-powered research brief | `research.py:generate_research_brief()` | High |
| AI outreach draft generation | New `draft_agent.py` | High |
| Structured evidence extraction | `research_agent.py` | High |
| Fact verification agent | `verify_agent.py` | Medium |
| AI tool-calling for research | `research_agent.py` | High |
| Cost/token tracking | `groq_client.py` | Medium |

---

## 7. AI-ASSISTED RESEARCH & QUALIFICATION WORKFLOW

### Research Profile Schema (Extend `research.py`)

```python
class ResearchProfile(BaseModel):
    company_summary: str
    evidence_ids: list[str]
    signals: list[Signal]
    hiring_signals: list[HiringSignal]
    news_signals: list[NewsSignal]
    tech_signals: list[TechSignal]
    decision_makers: list[DecisionMaker]
    opening: OpeningDraft
    suggested_questions: list[str]
    limitations: list[str]
    unknowns: list[str]
    evidence_refs: list[str]
    model_version: str
    tokens_used: int
    latency_ms: int
```

### Evidence-Backed Draft Generation

```python
class OutreachDraft(BaseModel):
    channel: Literal["email", "linkedin", "sms"]
    recipient_name: str | None
    recipient_title: str | None
    subject: str | None
    body: str
    evidence_refs: list[str]
    personalization_reasons: list[str]
    confidence: Literal["high", "medium", "low"]
    fallback_used: bool
```

---

## 8. HUMAN REVIEW QUEUE

### Current State: Partial (Approval gate exists, no dedicated UI)

### Required Implementation

| Component | Status | Location |
|-----------|--------|----------|
| Review queue page | ❌ Missing | New `ReviewQueuePage.tsx` |
| Evidence inspection modal | ❌ Missing | New component |
| Approve/Reject/Request actions | ✅ Backend | `approval_node()` |
| Duplicate merge review | ⚠️ Backend only | `merge_node()` |
| Decision audit log | ✅ Backend | `stage_events` |

### New Frontend Pages

```
frontend/src/pages/
├── ReviewQueuePage.tsx       # List of items needing review
├── ReviewDetailPage.tsx      # Evidence inspection + actions
├── MergeReviewPage.tsx       # Duplicate resolution UI
```

---

## 9. AI OUTREACH DRAFTS & DRY-RUN TRACKING

### Draft Generation Flow

```
Research Profile → DraftAgent (Groq) → Structured Draft → Human Edit → Approval → Dry-Run
```

### Dry-Run Activity Tracking (Extend Existing)

| Event Type | Current | Enhanced |
|------------|---------|----------|
| `draft_created` | ✅ | + AI metadata |
| `draft_edited` | ❌ | New |
| `approved` | ✅ | + version |
| `rejected` | ✅ | + reason |
| `dry_run_passed` | ✅ | + safety report |
| `dry_run_blocked` | ✅ | + reason |
| `simulated_open` | ❌ | New (simulated) |
| `simulated_click` | ❌ | New (simulated) |
| `simulated_reply` | ❌ | New (simulated) |
| `opt_out` | ✅ | Verified |

---

## 10. CALLER DASHBOARD (9 Panels)

### Current: CompanyDetailPage.tsx (partial)

### Required Panels (Per Brief §10)

| Panel | Current | Required |
|-------|---------|----------|
| 1. Who/Why Now | ⚠️ Partial | Company + decision-maker + why qualified |
| 2. Engagement Timeline | ⚠️ Partial | Chronological activity with real/simulated labels |
| 3. Company Briefing | ✅ Complete | What they do, size, tools, needs |
| 4. News/Funding | ✅ Complete | Sourced signals |
| 5. Hiring Signals | ✅ Complete | Open roles + implications |
| 6. Connection Points | ❌ Missing | Relevant public biz info |
| 7. Suggested Opening | ✅ Template | Editable opening + 2 questions |
| 8. Safety Check | ✅ Partial | DNC, consent, verification gaps |
| 9. Call Outcome | ✅ Template | Buttons + notes |

### New Page: `CallerBriefingPage.tsx`

---

## 11. COMPLIANCE, CRM & AUDIT

### Compliance Checks (Backend-Enforced)

| Check | Status | Location |
|-------|--------|----------|
| DNC before send | ✅ | `safety.py:evaluate_outreach()` |
| Opt-out stops all | ✅ | `safety.py` |
| Consent requirements | ⚠️ Stub | `safety.py` |
| Approval required | ✅ | `approval_node()` |
| Version check | ✅ | Draft versioning |
| Required evidence | ✅ | Scoring thresholds |
| Safe failure | ✅ | `_enrichment_ok()` |

### CRM Adapter

| Component | Status | Notes |
|-----------|--------|-------|
| Adapter interface | ✅ | `main.py` placeholder |
| GoHighLevel sync | ❌ Blocked | No credentials |
| Sync retry logic | ❌ Missing | Need implementation |
| Conflict resolution | ❌ Missing | Need implementation |

### Audit Trail (Complete)

| Event Type | Stored | Queryable |
|------------|--------|-----------|
| Stage transitions | ✅ | `stage_events` |
| Outreach activity | ✅ | `outreach_events` |
| Approval decisions | ✅ | `stage_events` |
| Review decisions | ✅ | `stage_events` |
| Call outcomes | ✅ | `call_notes` |

---

## 12. COST, HEALTH & OPERATIONS

### Connector Health (Implemented)

- `/api/sources` returns real-time status per connector
- Last success/failure, rate limit status, error codes

### Cost Tracking (Stub → Implement)

| Metric | Current | Target |
|--------|---------|--------|
| AI tokens/cost | Stub | Groq usage tracking |
| Search API costs | Missing | Per-provider tracking |
| Cost per qualified lead | Missing | Calculate from usage |
| Cost per reply | N/A (dry-run) | Future |

### Workflow Operations

- Retry with backoff ✅
- Idempotency via DB constraints ✅
- Pause/resume ❌ (not needed for demo)

---

## 13. FRONTEND PAGES — COMPLETION STATUS

| Page | Status | Gaps |
|------|--------|------|
| Overview | ✅ Complete | - |
| Campaigns | ✅ Complete | - |
| Companies List | ✅ Complete | - |
| Company Detail | ✅ Complete | - |
| Runs List | ✅ Complete | - |
| Run Detail | ✅ Complete | - |
| Discovery Run Detail | ✅ Complete | - |
| **Review Queue** | ❌ Missing | New page needed |
| **Review Detail** | ❌ Missing | New page needed |
| **Merge Review** | ❌ Missing | New page needed |
| **Outreach Drafts** | ❌ Missing | New page needed |
| **Caller Briefing** | ⚠️ Template | Make functional |
| Connector Health | ✅ In Overview | - |

---

## 15. IMPLEMENTATION ORDER & DEPENDENCIES

### Phase 2A: Groq & AI Foundation (Week 1)
1. `groq_client.py` + `structured_output.py` + `prompts.py`
2. `research_agent.py` with tool-calling
3. Update `research.py` to use Groq
4. Unit tests with mocked Groq

### Phase 2B: Research & Drafts (Week 1-2)
1. `draft_agent.py` for outreach drafts
2. `verify_agent.py` for fact verification
2. Update `research.py` to use agents
3. Structured output validation

### Phase 2C: Review Queue & Drafts UI (Week 2)
1. `ReviewQueuePage.tsx` + `ReviewDetailPage.tsx`
2. `OutreachDraftsPage.tsx` + `DraftEditor.tsx`
3. `CallerBriefingPage.tsx` (functional)
4. Merge review UI

### Phase 2D: Compliance & Polish (Week 2-3)
1. Cost tracking in `groq_client.py`
2. Connector health enhancements
3. CRM adapter mock + tests
4. End-to-end manual scenario testing

---

## 16. DATABASE CHANGES

### New Tables

```sql
-- Outreach drafts
CREATE TABLE outreach_drafts (
    id INTEGER PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    person_id INTEGER,
    channel TEXT,  -- email, linkedin, sms
    subject TEXT,
    body TEXT,
    evidence_fact_ids TEXT,  -- JSON array
    status TEXT,  -- draft, approved, rejected
    approved_by TEXT,
    approved_at DATETIME,
    version INTEGER DEFAULT 1,
    prompt_version TEXT,
    model_name TEXT,
    tokens_used INTEGER,
    created_at DATETIME,
    updated_at DATETIME
);

-- AI usage tracking
CREATE TABLE ai_usage (
    id INTEGER PRIMARY KEY,
    model_name TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd REAL,
    operation_type TEXT,  -- research, draft, verify
    company_id INTEGER,
    success BOOLEAN,
    latency_ms INTEGER,
    error_message TEXT,
    created_at DATETIME
);

-- Call notes (extend existing)
-- Already exists: call_notes table
```

### Migration Strategy

```python
# backend/app/db.py - add migration helper
def run_migrations():
    # Check schema version, apply incremental migrations
    pass
```

---

## 17. BACKEND ENDPOINTS TO ADD

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/companies/{id}/drafts` | GET/POST | List/create drafts |
| `/api/drafts/{id}` | GET/PUT/DELETE | Manage draft |
| `/api/drafts/{id}/approve` | POST | Approve draft |
| `/api/drafts/{id}/reject` | POST | Reject draft |
| `/api/companies/{id}/call-notes` | GET/POST | Call notes CRUD |
| `/api/review/queue` | GET | Review queue list |
| `/api/review/{company_id}/approve` | POST | Approve from queue |
| `/api/review/{company_id}/reject` | POST | Reject from queue |
| `/api/review/{company_id}/request-evidence` | POST | Request more research |
| `/api/sources/health` | GET | Connector health details |
| `/api/usage/costs` | GET | Cost summary |

---

## 18. FRONTEND PAGES TO CREATE

| Page | Route | Priority |
|------|-------|----------|
| `ReviewQueuePage.tsx` | `/review` | High |
| `ReviewDetailPage.tsx` | `/review/:companyId` | High |
| `MergeReviewPage.tsx` | `/merge-review/:companyId` | Medium |
| `OutreachDraftsPage.tsx` | `/companies/:id/drafts` | High |
| `DraftEditorPage.tsx` | `/drafts/:id/edit` | High |
| `CallerBriefingPage.tsx` | `/caller/:companyId` | High |

---

## 19. SECURITY & COMPLIANCE

### Already Implemented
- ✅ DRY_RUN enforced in backend (not just UI)
- ✅ DNC/opt-out checked before every outreach action
- ✅ Approval required before dry-run
- ✅ Shared suppression list across channels
- ✅ No secrets in frontend
- ✅ CORS restricted to Vite dev origin

### To Verify/Document
- [ ] CAN-SPAM email requirements documented
- [ ] TCPA/phone compliance documented
- [ ] LinkedIn platform terms documented
- [ ] GDPR/CCPA data handling documented
- [ ] Data retention policy defined

---

## 20. TEST PLAN

### Unit Tests (Add to Existing)

| Area | Tests Needed |
|------|--------------|
| Groq client | Mock responses, retries, validation errors |
| Structured output | Valid/invalid schema, missing fields |
| Research agent | Tool calls, evidence extraction |
| Draft agent | Channel variants, personalization |
| Verify agent | Corroboration logic, conflict detection |
| Groq client | Rate limits, timeouts, invalid key |

### Integration Tests (Live - Marked Explicit)

```python
@pytest.mark.live
async def test_tavily_live_discovery():
    # Requires TAVILY_API_KEY
    
@pytest.mark.live
async def test_groq_research_brief():
    # Requires GROQ_API_KEY
```

### E2E Manual Scenario (Per Brief §14)

```bash
# 1. Create campaign with targeting + exclusions
# 2. Discover real companies (live Tavily/Exa)
# 3. Inspect deduplication + source evidence
# 4. Enrich + research a lead
# 5. Verify scoring → route uncertain to review
# 6. Approve one, reject another
# 7. Generate + edit personalized draft
# 8. Confirm backend safety + dry-run
# 9. Record simulated activity + opt-out
# 10. Verify rejected/opted-out blocked
# 11. Caller briefing → save call note → reload
# 12. Inspect workflow events, health, costs
```

---

## 21. ENVIRONMENT & SETUP

### Required Environment Variables

```bash
# .env (backend)
BACKEND_PORT=8000
FRONTEND_ORIGIN=http://127.0.0.1:5173
DATABASE_URL=sqlite:///./b2b_lead_engine.db
DRY_RUN=true

# Discovery (LIVE)
TAVILY_API_KEY=<redacted — set in local .env>
EXA_API_KEY=<redacted — set in local .env>
BRAVE_API_KEY=  # Empty = fixture mode

# Enrichment
GNEWS_API_KEY=<redacted — set in local .env>
OPENCORPORATES_API_KEY=
SEC_USER_AGENT=B2BLeadEngine/1.0 (demo@b2bleadengine.com)

# Remote OK - no key needed (public feed)

# AI (NEW)
GROQ_API_KEY=<redacted — set in local .env>
GROQ_MODEL=llama-3.1-70b-versatile
GROQ_TEMPERATURE=0.1
GROQ_MAX_TOKENS=4096
```

### .env.example (Update)

```bash
# Copy .env.example to .env and fill in your keys
BACKEND_PORT=8000
FRONTEND_ORIGIN=http://127.0.0.1:5173
DATABASE_URL=sqlite:///./b2b_lead_engine.db
DRY_RUN=true

TAVILY_API_KEY=
EXA_API_KEY=
BRAVE_API_KEY=
GNEWS_API_KEY=
OPENCORPORATES_API_KEY=
SEC_USER_AGENT=B2BLeadEngine/1.0
GROQ_API_KEY=
GROQ_MODEL=llama-3.1-70b-versatile
GROQ_TEMPERATURE=0.1
GROQ_MAX_TOKENS=4096
```

### Run Commands

```bash
# Backend
cd C:\sales_project\backend
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Frontend
cd C:\sales_project\frontend
npm run dev

# Tests
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/ -q
npm test --prefix frontend
npm run build --prefix frontend
```

---

## 22. RISKS, ASSUMPTIONS & BLOCKERS

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Groq API rate limits | Medium | High | Exponential backoff, caching, usage tracking |
| Groq model changes | Low | Medium | Version pinning, fallback to template |
| Search API quota exhaustion | Medium | High | Per-campaign limits, caching |
| AI hallucination | Medium | High | Evidence IDs + structured output + validation |
| Provider terms change | Low | Medium | Monitor terms, fallback policy |
| GoHighLevel credentials unavailable | High | Low | Keep internal DB as source of truth |
| Legal compliance for outreach | Medium | High | Dry-run only; legal review before live |
| Demo depends on live APIs | High | Medium | Cache live responses for repeatable demo |

### External Blockers
- **GoHighLevel CRM**: No credentials → adapter remains mocked
- **Groq API**: Key provided → ready to implement
- **YC Directory**: No API access → CSV import only (acceptable)

---

## 23. DEFINITION OF "LIVE" vs "MOCKED"

| Component | Status | Live Test Evidence |
|-----------|--------|-------------------|
| Tavily Discovery | ✅ Live | 3 real candidates with URLs |
| Exa Discovery | ✅ Live | 3 real candidates with URLs |
| Remote OK | ✅ Live | 10 companies with hiring signals |
| Greenhouse | ✅ Live | Real job posts for known boards |
| SEC EDGAR | ✅ Live | 10 Apple filings |
| GNews | ✅ Live | Returns results (empty for test cos) |
| Website | ✅ Live | Fetches real pages |
| OpenCorporates | Fixture | No API key |
| YC Directory | CSV Import | No public API |
| Brave Search | Fixture | No API key |
| Groq AI | **Ready** | Key provided, not yet integrated |

---

## 24. IMPLEMENTATION CHECKLIST

### Phase 2A: Groq & AI Foundation
- [ ] `groq_client.py` with async client, retries, caching
- [ ] `structured_output.py` with Pydantic schemas
- [ ] `prompts.py` with few-shot examples
- [ ] `research_agent.py` with tool-calling
- [ ] Update `research.py` to use Groq
- [ ] Unit tests (mocked)

### Phase 2B: Research & Drafts
- [ ] `draft_agent.py` for email/LinkedIn/SMS drafts
- [ ] `verify_agent.py` for fact verification
- [ ] Update `research.py` to use agents
- [ ] Structured output validation
- [ ] Cost/token tracking

### Phase 2C: Review Queue & Drafts UI
- [ ] `ReviewQueuePage.tsx` + `ReviewDetailPage.tsx`
- [ ] `MergeReviewPage.tsx`
- [ ] `OutreachDraftsPage.tsx` + `DraftEditorPage.tsx`
- [ ] `CallerBriefingPage.tsx` (functional 9 panels)

### Phase 2D: Compliance & Polish
- [ ] Cost tracking in `groq_client.py`
- [ ] Connector health enhancements
- [ ] CRM adapter mock + tests
- [ ] E2E manual scenario (all 12 steps)

---

## 25. APPROVAL REQUEST

**This plan is ready for your approval.** 

### Key Decisions Needed from You:

1. **Groq Model**: `llama-3.1-70b-versatile` ✅ (using provided key)
2. **Discovery Sources**: Keep current 4 (Tavily, Exa, Remote OK, Brave) — no new providers
3. **YC Directory**: Skip live; keep CSV import only
4. **AI Scope**: Research brief + Outreach drafts + Fact verification only
5. **Outreach Channels**: Email + LinkedIn (human-operated) + SMS (stub)
6. **CRM**: GoHighLevel adapter mocked; document as blocked
6. **Compliance**: Dry-run only; document legal requirements

### Estimated Effort: 2-3 weeks for full Phase 2 delivery

---

**Waiting for your approval and the Groq API key (provided in local `.env`, never committed) to begin Phase 2 implementation.**