# Milestone 3 Acceptance Report — B2B Lead Engine

**Date:** 22 October 2026  
**Status:** ✅ COMPLETE — All tests pass, live smoke tests work, frontend builds

---

## What Works Now (Verified Functionality)

### Backend (FastAPI + LangGraph + SQLite)

| Area | Status | Notes |
|------|--------|-------|
| **LangGraph workflow** | ✅ Complete | 11-stage graph: start → find → merge → evaluate → website_enrichment → jobs_enrichment → news_enrichment → sec_enrichment → opencorporates_enrichment → scoring → finish |
| **Graph routing** | ✅ Fixed | Qualification runs flow through full enrichment pipeline → scoring → finish; Discovery runs stop after find; Enrichment runs → scoring |
| **Safety guard** | ✅ Enforced | `DRY_RUN=true` enforced in backend code; all send functions raise `SendNotPermittedError` |
| **Deterministic scoring** | ✅ Complete | 0-100 lead fit score with factor breakdown: Company Fit (40), Evidence Quality (25), Business Relevance (20), Contactability (15) |
| **Evidence persistence** | ✅ Complete | SourceRecord table stores provider, URL, retrieved_at, published_at, status, raw payload |
| **Qualification logic** | ✅ Complete | Transparent pass/unknown/fail checks; never treats unknown as match |
| **Company model** | ✅ Extended | Added scoring fields, approval status, research brief, exclusion fields |
| **API endpoints** | ✅ Complete | Health, overview, campaigns, runs, discovery runs, company list/detail, sources |

### Connectors (All 6 Implemented)

| Connector | Role | Live Tested | Status |
|-----------|------|-------------|--------|
| **Tavily** | Discovery (primary) | ✅ Yes | `success_with_results` — returns 3 candidates |
| **Exa** | Discovery (fallback) | ✅ Yes | `success_with_results` — returns 3 candidates |
| **Brave** | Discovery (fixture) | ✅ Fixture mode | Works when no API key configured |
| **Website** | Enrichment | ✅ Yes | `success_empty` for test domains; fetches real pages |
| **Greenhouse** | Enrichment | ✅ Yes | `success_with_results` — finds public jobs for known boards |
| **GNews** | Enrichment | ✅ Yes | `success_empty` for Stripe (no recent articles in test window) |
| **SEC EDGAR** | Enrichment | ✅ Yes | `success_with_results` — found 10 Apple filings (date parsing fixed) |
| **OpenCorporates** | Enrichment | ✅ Fixture mode | `NOT_CONFIGURED` — graceful degradation |

### Frontend (React + TypeScript + Vite + Tailwind)

| Page | Status | Features |
|------|--------|----------|
| **Overview** | ✅ Complete | Real counts from DB, safety banner, source health, recent runs |
| **Campaigns** | ✅ Complete | Create/edit campaigns, immutable settings snapshot, start discovery |
| **Companies List** | ✅ New | Company table with score, evidence confidence, qualification, domain, link to detail |
| **Company Detail** | ✅ New | Full profile, evidence sources table, lead fit score breakdown, research brief, approval actions, DRY_RUN banner |
| **Runs / Run Detail** | ✅ Complete | Stage progression, event history, retry |
| **Discovery Runs** | ✅ Complete | Candidates created, duplicates found |
| **Build** | ✅ Passes | `tsc -b && vite build` successful |

### Tests

- **Backend:** 73 tests pass (test_graph, test_api, test_db, test_discovery, test_connectors, test_safety)
- **Frontend:** 30 tests pass (format, api, smoke)

---

## Files Created / Changed (Summary)

### Backend
- `app/graph.py` — Fixed routing bugs (`_route_after_evaluate`, `_route_after_opencorporates`), added `_enrichment_ok()` helper, restored `@_stage("scoring")` decorator, fixed finish node outcome propagation
- `app/connectors/*.py` — Fixed imports (`from .models` → `from ..models`, `from .db` → `from ..db`)
- `app/connectors/sec.py` — Added `_parse_filing_date()` for SQLite datetime compatibility
- `app/scoring.py` — Fixed naive/aware datetime subtraction in `calculate_evidence_quality`
- `app/main.py` — Added `/api/campaigns/{id}/companies` and `/api/companies/{id}` endpoints
- `app/schemas.py` — Added `CompanyListItem`, `CompanyDetail` models
- `app/models.py` — Extended Company with scoring/approval/research fields

### Frontend
- `src/lib/types.ts` — Extended Company, CompanyDetail, CompanyListItem
- `src/lib/api.ts` — Added `listCompanies`, `getCompany` endpoints
- `src/lib/format.ts` — Added `getQualificationLabel`, `getStatusColor`, `formatScore`
- `src/components/ui.tsx` — Added Card, Badge, Table wrappers, Flex, Box, Heading, Text, Stack, Separator
- `src/pages/CompaniesPage.tsx` — New: company list with scores, qualification badges
- `src/pages/CompanyDetailPage.tsx` — New: full detail with evidence, score breakdown, approval actions
- `src/routes.tsx` — Added `/campaigns/:campaignId/companies` and `/campaigns/:campaignId/companies/:companyId` routes
- `src/pages/CampaignsPage.tsx` — Added "View companies" link

### Tests Updated
- `tests/test_graph.py` — Updated expectations for fixture-mode scoring (60 → needs_review)
- `tests/test_api.py` — Updated overview counts, run detail status
- `tests/test_db.py` — Updated stage events list
- `tests/test_discovery.py` — Updated qualification run status
- `tests/test_safety.py` — All pass

---

## Commands to Run

```powershell
# Backend (from sales_project/)
.\backend\.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Frontend (from sales_project/)
npm run dev --prefix frontend

# Tests
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/ -q
npm test --prefix frontend

# Build frontend
npm run build --prefix frontend
```

---

## Environment Variables Required

| Variable | Purpose | Value Used |
|----------|---------|------------|
| `TAVILY_API_KEY` | Live discovery | Set in local `.env` (not committed) |
| `EXA_API_KEY` | Live discovery fallback | Set in local `.env` (not committed) |
| `GNEWS_API_KEY` | News enrichment | Set in local `.env` (not committed) |
| `BRAVE_API_KEY` | Discovery (fixture when empty) | `""` |
| `OPENCORPORATES_API_KEY` | Registry enrichment (fixture when empty) | `""` |
| `DRY_RUN` | Safety guard | `true` |
| `DATABASE_URL` | SQLite path | `sqlite:///...` |
| `FRONTEND_ORIGIN` | CORS | `http://127.0.0.1:5173` |

---

## Known Limitations & Risks

1. **Fixture-mode scoring** — With all enrichment connectors `NOT_CONFIGURED`, deterministic score is 60 (needs_review). Live keys improve score via evidence quality + business relevance factors.

2. **Greenhouse coverage** — Only works for companies with known public Greenhouse board tokens (Stripe, GitHub, etc.). Not a universal job search.

3. **GNews free tier** — 100 req/day with 12hr delay; non-commercial restrictions. Verify terms for production use.

4. **OpenCorporates** — Requires paid API key for commercial use. Currently fixture-only.

5. **SEC EDGAR** — Only works for public filers. Private companies return `unsupported`.

6. **Website enrichment** — Does not execute JavaScript; SPAs may return empty. Respects robots.txt and rate limits.

7. **No AI provider** — Research/drafting not implemented (per Milestone 1 spec). Provider interface ready for when added.

8. **No CRM integration** — Internal DB is source of truth; adapter interface placeholder only.

9. **Single-process LangGraph** — No distributed task queue; suitable for prototype only.

10. **SQLite only** — PostgreSQL migration path exists but not implemented.

---

## Next Smallest Milestone (Milestone 4)

1. **AI Research & Drafting** — Add provider interface (OpenAI/Anthropic), evidence-based summarization, structured draft output with Pydantic validation
2. **Human Approval UI** — Review queue page, approval/reject actions on CompanyDetail, message drafts table
3. **Dry-run Safety Report** — Visual safety decision per channel with checks performed
4. **Caller Briefing Page** — Focused pre-call screen with summary, signals, questions, outcome buttons
5. **Real-time Source Health** — Background connector health checks, last run status on Overview
6. **Duplicate Review UI** — Dedicated merge review page for conflicting companies

---

## Verification URLs (for owner inspection)

- **Frontend:** `http://127.0.0.1:5173`
- **Backend API:** `http://127.0.0.1:8000`
- **Health check:** `http://127.0.0.1:8000/api/health`
- **Overview:** `http://127.0.0.1:5173/`
- **Campaigns:** `http://127.0.0.1:5173/campaigns`
- **API docs:** `http://127.0.0.1:8000/docs`