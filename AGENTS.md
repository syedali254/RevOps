# OpenCode Project Instructions — B2B Lead Engine

## First read
Before changing code, read `plan.md` from beginning to end, then inspect the existing repository. Treat `plan.md` as the project specification, but do not assume every provider has a free tier or that every source covers every company.

## Confirmed stack (owner-decided — do not substitute without asking)

| Area | Decision |
|---|---|
| Frontend | React + TypeScript + Vite in `frontend/` |
| Backend | Python + FastAPI in `backend/` |
| Orchestration | **LangGraph** — owns workflow state, nodes, conditional routing, run history |
| Database | SQLite + SQLAlchemy (PostgreSQL only later, if justified) |
| Python env | Project-local `backend/.venv` |
| Styling | Tailwind CSS if it installs cleanly; otherwise organized CSS modules / one clean design system |
| UI components | One accessible component system if setup is straightforward; never multiple overlapping libraries |
| Tests | `pytest` for backend; lightweight frontend tests (Vitest) where useful |
| AI | No AI provider in Milestone 1; add a provider interface when research/drafting arrives |

**Prohibited:** n8n (do not install or use it), a separate custom Python stage-runner/orchestration engine, PostgreSQL/Docker/Redis/Celery in Milestone 1, and multiple AI agents added for appearance.

**Frontend/backend boundary:** React calls FastAPI through one typed API client over HTTP/JSON. Secrets, database access, provider calls, and all qualification/confidence/safety decisions stay on the backend. Local CORS allows only the Vite dev origin.

**Agreed hybrid workflow:** discovery sources return many candidates → normalize and merge duplicates into one company record per company (evidence preserved) → enrichment sources investigate those discovered companies → business directories/datasets may add candidates or corroborate facts → qualify, verify, and separate target fit from evidence confidence and safety status → uncertain or conflicting records go to human review → evidence-based research and draft → human approval → dry-run safety gate (always no-send) → caller briefing.

## Project goal
Build a credible, working prototype of the B2B Lead Engine described in `plan.md`. Prioritize a complete, demonstrable workflow with real source evidence, transparent uncertainty, safe failure handling, human approval, dry-run-only outreach, and a caller briefing.

## Non-negotiable rules
1. Do not invent companies, people, job posts, news, emails, phone numbers, source URLs, or engagement events.
2. Every externally sourced fact must retain its source URL and retrieval timestamp.
3. Keep target fit, evidence confidence, and safety status separate.
4. Unknown or conflicting facts must remain unknown/conflicting until reviewed. Never silently mark them verified.
5. Do not send real emails, SMS, LinkedIn/social messages, or website-form submissions. The initial prototype is dry-run only. Enforce this in backend logic, not just the UI.
6. Do not scrape behind logins, bypass access controls, or automate LinkedIn/social actions.
7. Never put API keys in frontend code or commit secrets. Use `.env` and `.env.example`; ensure `.env` is gitignored.
8. Every source connector must distinguish successful empty results from timeout, rate limit, authentication error, blocked access, and parsing failure.
9. Use bounded timeouts/retries, caching where appropriate, structured logs, and idempotent operations.
10. Do not build all five connectors at once. Implement and test one at a time.
11. Prefer free/official/public access paths, but verify provider terms and coverage before integrating. Do not claim a provider is free for commercial use without evidence.
12. Do not add unnecessary agents, frameworks, or infrastructure just to make the architecture look advanced.

## Frontend design requirements (high priority)
Build a restrained, professional B2B SaaS look: light surfaces, dark readable type, one accent color, subtle borders, consistent spacing and typography, accessible contrast and focus states, responsive on laptop screens. Reusable shell: left sidebar, top bar, main content area, shared components for buttons, inputs, tables, status indicators, empty states, and page headers.

Avoid: card/badge/gradient/icon overload, giant headings, fabricated charts or metrics, emoji as icons, arbitrary colors, crowded tables, unrelated-template dashboards.

All metrics must come from real API responses with honest loading/empty/success/error states. Distinguish test data from real data. Keep styling organized (design tokens + small components) so a separate agent can refine visuals without touching backend logic. **Never claim the UI has been visually validated — report build results and the URLs for the owner to inspect.**

## Development approach
- Start by inspecting the repository, available runtimes, existing files, and current git status.
- Do not overwrite or delete existing user work.
- Before implementation, summarize the existing state, identify missing prerequisites, and propose the smallest first milestone.
- Implement in small, testable steps. After each step, run relevant tests and report actual results.
- Use typed models and clear module boundaries.
- Keep source retrieval, normalization, deduplication, verification rules, AI summaries, workflow control, and UI responsibilities separate.
- Use fixtures/mocks in tests so tests do not require live APIs or consume quotas.
- Keep the app usable if an API key is absent: show the connector as unconfigured and explain how to configure it.
- Do not claim any integration works until its live request or a clearly labeled local fixture test has actually succeeded.

## Milestone 1 — runnable foundation (do not exceed it)
Do not build the whole product immediately. Milestone 1 is:
1. Reinspect the directory before editing.
2. Update `plan.md` / `AGENTS.md` if the architecture changes.
3. Create `backend/` and `frontend/` with the confirmed stack above.
4. Backend: configuration handling, SQLite initialization, SQLAlchemy models for campaigns, companies, source/evidence records, workflow runs, and stage events.
5. Backend: a small **real LangGraph workflow** with explicit state, nodes, conditional routing, and honest outcomes (`continue`, `needs_human_review`, `stopped_after_error`).
6. Backend: health, campaign, overview, and workflow-run endpoints; structured event history with timestamps and statuses.
7. Backend: the global dry-run/no-send guard, enforced in code.
8. Frontend: application shell, navigation, Overview / Campaigns / Workflow runs / Run details, real API calls, loading/empty/success/error states, test-data labelling, and the persistent `DRY RUN — NO MESSAGES SENT` banner.
9. Tests for database behavior, graph transitions, failure paths, and the safety guard; run the frontend build.
10. Stop and report the exact files changed, commands run, test results, URLs to open, and next step.

Out of scope for Milestone 1: the five source connectors, AI research/drafting, live outreach, review-queue UI, caller briefing, CRM.

Do not start the source connectors until the user confirms Milestone 1 works.

## Completion reporting
At the end of each milestone, report:
- What works now (only verified functionality).
- Files created/changed.
- Commands to run the app and tests.
- Environment variables or accounts required.
- Tests run and their actual results.
- Known limitations and risks.
- The next smallest milestone.

Do not claim the entire product is complete when only the skeleton is built.
