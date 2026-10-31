# B2B Lead Engine — Milestone 1

A locally hosted, evidence-first B2B lead workflow prototype.  
**Dry-run only — this build never sends messages to real people.**

## Stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Vite (in `frontend/`) |
| Backend | Python + FastAPI (in `backend/`) |
| Orchestration | LangGraph (in-process, owns workflow state) |
| Database | SQLite + SQLAlchemy |
| Python env | `backend/.venv` (project-local) |
| Styling | Tailwind CSS (design tokens in `src/index.css`) |
| Tests | `pytest` (backend) / Vitest + React Testing Library (frontend) |

## Quick start (Windows PowerShell)

```powershell
cd C:\sales_project

# Backend (terminal A)
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend (terminal B)
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173** in a browser.

## Running tests

```powershell
# Backend
cd C:\sales_project\backend
.\.venv\Scripts\python.exe -m pytest

# Frontend
cd C:\sales_project\frontend
npm run test
npm run typecheck
npm run lint
```

## What works in Milestone 1

- **Campaigns** — create a campaign with sector, country, size, titles, exclusions. Saved as an immutable settings snapshot.
- **Workflow runs** — start a LangGraph run for a hand-entered company (labelled **Test data**).
- **Graph stages** — `start → find → merge → evaluate → (finish | hold_for_review | reject | stop_after_error)`.
- **Honest outcomes** — `continue`, `needs_human_review`, `stopped_after_error`, `rejected`.
- **Review paths** — missing required fields, duplicate domains, unknown employee ranges all halt the run and show the reason.
- **Failure injection** — `fail_at` query param forces a stage to fail for demo purposes.
- **Event log** — every stage writes a `stage_events` row with timestamps, status, and details.
- **Overview** — live database counts, source health (all `not_configured`), safety banner, next actions.
- **Dry-run guard** — every channel's send function raises `SendNotPermittedError`. The UI banner is not decoration; the backend enforces it.
- **CORS** — allows only `http://127.0.0.1:5173` / `http://localhost:5173`.

## Files created / changed

### Root
- `.gitignore` — ignores `.env`, `.venv`, `*.db`, `node_modules`, `dist`, editor files
- `.env.example` — documented template with `DRY_RUN=true`
- `AGENTS.md` — updated with confirmed stack and frontend design requirements
- `plan.md` — updated with confirmed stack, prohibited tools, frontend/backend boundary, hybrid workflow summary

### Backend (`backend/`)
```
backend/
├── requirements.txt
├── pytest.ini
├── .venv/                   # project-local virtual env
├── app/
│   ├── __init__.py
│   ├── config.py            # Pydantic settings from .env
│   ├── db.py                # Engine, session, init_db()
│   ├── models.py            # Campaign, Company, SourceRecord, WorkflowRun, StageEvent
│   ├── schemas.py           # Pydantic request/response models
│   ├── safety.py            # DRY_RUN guard, send_*() always raise
│   ├── graph.py             # LangGraph StateGraph + runner
│   └── main.py              # FastAPI endpoints
└── tests/
    ├── conftest.py
    ├── test_safety.py       # 9 tests — guard cannot be bypassed
    ├── test_db.py           # 9 tests — persistence, settings snapshots, evidence rows
    ├── test_graph.py        # 16 tests — routing, review, rejection, failure
    └── test_api.py          # 20 tests — health, overview, runs, CORS
```

### Frontend (`frontend/`)
```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── .env.example
├── .oxlintrc.json
├── index.html
├── public/favicon.svg
├── src/
│   ├── main.tsx
│   ├── index.css            # design tokens + base styles
│   ├── App.tsx
│   ├── routes.tsx
│   ├── smoke.test.tsx       # 11 render/behavior tests
│   ├── components/
│   │   ├── AppShell.tsx     # shell + nav + DRY RUN banner
│   │   └── ui.tsx           # Button, StatusPill, Table, Field, EmptyState, ErrorState, TestTag…
│   ├── hooks/useAsync.ts    # data-fetching hook with loading/error/retry
│   ├── lib/
│   │   ├── types.ts         # API response types (mirror Pydantic)
│   │   ├── api.ts           # single typed client, ApiError
│   │   ├── api.test.ts      # 6 tests
│   │   ├── format.ts        # status/outcome labels, duration, date formatting
│   │   └── format.test.ts   # 16 tests
│   └── pages/
│       ├── OverviewPage.tsx
│       ├── CampaignsPage.tsx
│       ├── RunsPage.tsx
│       └── RunDetailPage.tsx
```

## Verified test results

```
Backend:   54 passed in ~7s
Frontend:  30 passed in ~4s (22 unit + 11 render)
Typecheck: clean
Lint:      clean
Build:     production bundle ~298 kB JS + 22 kB CSS (gzipped ~92 kB)
```

## URLs to inspect

| Screen | URL |
|---|---|
| Overview | http://127.0.0.1:5173/ |
| Campaigns | http://127.0.0.1:5173/campaigns |
| Workflow runs | http://127.0.0.1:5173/runs |
| Run detail (e.g.) | http://127.0.0.1:5173/runs/1 |

## Known limitations (by design, Milestone 1 scope)

- **No source connectors** — discovery/enrichment sources are listed with status `not_configured`. The graph records that fact honestly instead of faking results.
- **No AI** — research/drafting is not implemented; a provider interface will be added in a later milestone.
- **No review queue UI** — `needs_human_review` runs are visible in the run list and detail; a dedicated queue comes later.
- **No caller briefing** — the briefing page is out of scope for Milestone 1.
- **No CRM** — internal SQLite is the source of truth; a CRM adapter will be added when the owner confirms GoHighLevel (or another).
- **Test data only** — every company is entered manually and labelled `test_seed`. Real retrieved data arrives with the first connector.
- **No PostgreSQL / Docker / Redis / Celery** — SQLite and in-process LangGraph keep the prototype runnable on a laptop.

## Next milestone (recommended)

**M2 — Source 1: Web search discovery**

1. Add Brave Search API key to `.env` (after the owner signs up and confirms terms).
2. Implement a `DiscoveryConnector` that returns candidate companies with source URLs and timestamps.
3. Wire it into the graph's `find` node so candidates flow into the same `companies` table.
4. Add domain normalization + initial duplicate detection (already exercised by the merge stage).
5. Keep tests fixture-based so they run without a live key.

Only one connector at a time — the plan explicitly forbids building all five in parallel.

---

*Do not claim visual validation — the author will inspect the running application at the URLs above.*