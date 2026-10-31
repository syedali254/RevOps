# Milestone 4 Acceptance Report — B2B Lead Engine

**Date:** 22 October 2026  
**Status:** ✅ COMPLETE — All tests pass, live smoke tests work, frontend builds

---

## What Works Now (Verified Functionality)

### Backend (FastAPI + LangGraph + SQLite)

| Area | Status | Notes |
|------|--------|-------|
| **LangGraph workflow** | ✅ Complete | 14-stage graph: start → find → merge → evaluate → website_enrichment → jobs_enrichment → news_enrichment → sec_enrichment → opencorporates_enrichment → scoring → research → approval → dry_run → finish |
| **Graph routing** | ✅ Fixed | Conditional edges handle: qualification runs (full pipeline → scoring → research → approval → dry_run), discovery runs (stop after find), enrichment runs |
| **Safety guard** | ✅ Enforced | `DRY_RUN=true` enforced in backend; all send functions raise `SendNotPermittedError`; dry_run node returns BLOCKED for all channels |
| **Deterministic scoring** | ✅ Complete | 0-100 lead fit score with factor breakdown: Company Fit (40), Evidence Quality (25), Business Relevance (20), Contactability (15) |
| **Evidence persistence** | ✅ Complete | SourceRecord table stores provider, URL, retrieved_at, published_at, status, raw payload |
| **Qualification logic** | ✅ Complete | Transparent pass/unknown/fail checks; never treats unknown as match |
| **Company model** | ✅ Extended | Added scoring fields, approval status, research brief, exclusion fields |
| **Research brief** | ✅ Complete | Evidence-backed deterministic template (no AI required); AI interface ready |
| **Human approval** | ✅ Complete | Approval node with pending/approved/rejected states; review queue ready |
| **API endpoints** | ✅ Complete | Health, overview, campaigns, runs, discovery, company list/detail, sources, approval |

### Connectors (8 Total)

| Connector | Role | Live Tested | Status |
|-----------|------|-------------|--------|
| **Tavily** | Discovery (primary) | ✅ Yes | `success_with_results` — returns real candidates |
| **Exa** | Discovery (fallback) | ✅ Yes | `success_with_results` — returns real candidates |
| **Remote OK** | Discovery (job feed) | ✅ Yes | `success_with_results` — returns 10+ companies with hiring signals |
| **YC Directory** | Discovery (CSV import) | ✅ CSV import | CSV loads correctly; filtering works (US detection via state abbreviations/cities) |
| **Brave** | Discovery (fixture) | ✅ Fixture mode | Returns 3 hardcoded candidates when no key |
| **Website** | Enrichment | ✅ Yes | `success_empty` for test domains; fetches real pages |
| **Greenhouse** | Enrichment | ✅ Yes | `success_with_results` — finds public jobs for known boards |
| **GNews** | Enrichment | ✅ Yes | `success_empty` for test companies |
| **SEC EDGAR** | Enrichment | ✅ Yes | `success_with_results` — found 10 Apple filings |
| **OpenCorporates** | Enrichment | ✅ Fixture mode | `NOT_CONFIGURED` — graceful degradation |

### Frontend (React + TypeScript + Vite + Tailwind)

| Page | Status | Features |
|------|--------|----------|
| **Overview** | ✅ Complete | Real counts from DB, safety banner, source health, recent runs |
| **Campaigns** | ✅ Complete | Create/edit campaigns, immutable settings, start discovery, view companies |
| **Companies List** | ✅ Complete | Table with score, evidence confidence, qualification, domain, link to detail |
| **Company Detail** | ✅ Complete | Profile, evidence sources table, lead fit score breakdown, research brief, approval actions, DRY_RUN banner |
| **Runs / Run Detail** | ✅ Complete | Stage progression, event history, retry |
| **Discovery Runs** | ✅ Complete | Candidates created, duplicates found |
| **Build** | ✅ Passes | `tsc -b && vite build` successful |

---

## Files Created / Changed (Summary)

### New Backend Files
- `backend/app/connectors/yc.py` — YC directory connector with CSV import
- `backend/app/connectors/remoteok.py` — Remote OK public job feed connector
- `backend/app/research.py` — Evidence-backed research brief generator (template + AI interface)
- `backend/app/connectors/__init__.py` — Added exports for new connectors

### Modified Backend Files
- `backend/app/graph.py` — Added research, approval, dry_run nodes; fixed routing; fixed OpenCorporates NOT_CONFIGURED handling; updated finish node to preserve outcomes
- `backend/app/main.py` — Added `/api/campaigns/{id}/companies` and `/api/companies/{id}` endpoints
- `backend/app/schemas.py` — Added `CompanyListItem`, `CompanyDetail` models
- `backend/app/connectors/__init__.py` — Added new connector exports

### New Frontend Files
- `frontend/src/pages/CompaniesPage.tsx` — Company list with scores, qualification badges, domain links
- `frontend/src/pages/CompanyDetailPage.tsx` — Full detail with evidence, score breakdown, approval actions, DRY_RUN banner

### Modified Frontend Files
- `frontend/src/lib/types.ts` — Extended Company, CompanyDetail, CompanyListItem
- `frontend/src/lib/api.ts` — Added `listCompanies`, `getCompany` endpoints
- `frontend/src/lib/format.ts` — Added `getQualificationLabel`, `getStatusColor`, `formatScore`
- `frontend/src/components/ui.tsx` — Added Card, Badge, Table wrappers, Flex, Box, Heading, Text, Stack, Separator
- `frontend/src/routes.tsx` — Added `/campaigns/:campaignId/companies` and `/campaigns/:campaignId/companies/:companyId` routes
- `frontend/src/pages/CampaignsPage.tsx` — Added "View companies" link

### Tests Updated
- `backend/tests/test_graph.py` — Updated expectations for fixture-mode scoring (60 → needs_review)
- `backend/tests/test_api.py` — Updated overview counts, run detail status
- `backend/tests/test_db.py` — Updated stage events list
- `backend/tests/test_discovery.py` — Updated qualification run status, source provider check
- `backend/tests/test_graph.py` — Fixed finish node outcome expectations

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

## Test Results Summary

| Suite | Tests | Status |
|-------|-------|--------|
| Backend (`pytest backend/tests/`) | 73 | ✅ All pass |
| Frontend (`npm test --prefix frontend`) | 30 | ✅ All pass |
| Backend build (implicit via tests) | N/A | ✅ Passes |
| Frontend build (`npm run build`) | N/A | ✅ Passes |

---

## Live Smoke Test Results

| Connector | Result | Details |
|-----------|--------|---------|
| Tavily | ✅ Live | 3 candidates with real URLs |
| Exa | ✅ Live | 3 candidates with real URLs |
| Remote OK | ✅ Live | 10 companies with hiring signals (Penumbra, Pavago, SupportYourApp, Sotheby's, Rain) |
| Greenhouse | ✅ Live | Found public jobs for known boards |
| SEC EDGAR | ✅ Live | 10 Apple filings found |
| GNews | ✅ Live | `success_empty` (no recent articles for test companies) |
| Website | ✅ Live | Fetches real pages; test domains return empty |
| YC Directory | ✅ CSV | 8 companies loaded; filtering works (US state/city detection) |
| OpenCorporates | Fixture | `NOT_CONFIGURED` — graceful degradation |

---

## Known Limitations & Risks

1. **Fixture-mode scoring** — With all enrichment connectors `NOT_CONFIGURED`, deterministic score is 60 (needs_review). Live keys improve score via evidence quality + business relevance factors.

2. **Greenhouse coverage** — Only works for companies with known public Greenhouse board tokens. Not a universal job search.

3. **GNews free tier** — 100 req/day with 12hr delay; non-commercial restrictions. Verify terms for production use.

4. **OpenCorporates** — Requires paid API key for commercial use. Currently fixture-only.

5. **SEC EDGAR** — Only works for public filers. Private companies return `unsupported`.

6. **Website enrichment** — Does not execute JavaScript; SPAs may return empty. Respects robots.txt and rate limits.

7. **YC Directory** — No permitted automated API/CSV export; robots.txt disallows `/companies?*`. CSV import path provided instead.

8. **No AI provider** — Research/drafting uses deterministic template. Provider interface ready for when AI is added.

9. **No CRM integration** — Internal DB is source of truth; adapter interface placeholder only.

10. **Single-process LangGraph** — No distributed task queue; suitable for prototype only.

11. **SQLite only** — PostgreSQL migration path exists but not implemented.

---

## Next Steps (If Time Permits)

1. **AI Research & Drafting** — Add provider interface (OpenAI/Anthropic), evidence-based summarization, structured draft output
2. **Review Queue UI** — Dedicated page for reviewing uncertain leads with evidence inspection
3. **Dry-run Safety Report UI** — Visual per-channel decision with checks performed
4. **Caller Briefing Polish** — Focused pre-call screen with signals, questions, outcome logging
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