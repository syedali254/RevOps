# B2B Lead Engine — Product & Implementation Plan

**Prepared:** 20 October 2026  
**Purpose:** Build a credible, end-to-end prototype for the take-home project, with working differentiating features and a clear path toward a controlled pilot.  
**Primary source:** *B2B Lead Engine: Developer Project Guideline* (19 October 2026).  
**Status:** Implementation proposal; provider availability, terms, and legal requirements must be rechecked before any production use.

---

## 1. Executive recommendation

Build a **small, complete lead workflow**, not a large collection of half-finished integrations.

The product should demonstrate this journey:

1. A user creates a campaign and chooses target companies.
2. The system finds real companies through enabled data sources.
3. Results from different sources are combined into one company record.
4. Each important fact shows its source, date, and verification status.
5. The system explains why the company fits, what is uncertain, and what needs human review.
6. It researches the company, relevant hiring/news signals, and a decision maker where reliable public evidence is available.
7. AI drafts a specific opening and questions using that evidence.
8. A human approves, edits, or rejects the draft.
9. A dry-run outreach screen shows what would happen without sending real messages.
10. The caller gets a briefing with company facts, evidence, recent signals, safety checks, and a place to record call outcomes.

**The key product promise:** *Every lead has a reason, every important claim has evidence, and every unsafe or uncertain step has a visible stop.*

This is a stronger differentiator than claiming to have many AI agents. It can be demonstrated live and is directly aligned with the guideline.

### What “working prototype” means

- Real data from working connectors, not invented companies or placeholder results.
- Source links and retrieval dates visible to the user.
- Functional search, filtering, deduplication, review, approval, and call notes.
- Failures and partial results are visible; one failed source does not silently create false certainty.
- No real outreach is sent in the initial prototype.
- API keys and credentials stay on the backend.
- A small test campaign can be completed from beginning to end.

It does **not** mean the prototype already has reliable access to every decision maker, verified mailbox existence for every email, all social integrations, production deliverability, or legal clearance for live outreach. Those require specific providers, permissions, testing, and budget.

---

## 2. Requirements taken from the project guideline

The guideline describes a locally hosted system that finds B2B technology companies, enriches and verifies records, researches companies and decision makers, prepares compliant outreach, tracks engagement, and gives callers a single briefing. A human closes the deal.

### Target settings

Starting defaults:
- Sector: B2B technology companies; editable sub-sectors.
- Employee range: 20–200; editable.
- Country: United States first; future countries should not require a rebuild.
- Decision-maker titles: Founder, CEO, operations and sales leaders, IT heads; editable.
- Exclusions: existing clients, competitors, and a shared do-not-contact (DNC) list.
- Each campaign keeps its own copy of its settings so results can be compared.

### Data and verification

For each company, aim to collect:
- Legal/company name, website/domain, size, location, sector.
- Phone system, if known and supported by evidence.
- Relevant decision makers and their titles, where a permitted source can support them.

Verification requirements:
- Important company facts should be checked through at least two sources before being marked verified.
- Email format/domain/mailbox checks must not send an email.
- Phone type/carrier should be checked if that capability is available.
- Current employer/title should be checked rather than assumed.
- Duplicate companies should be merged.
- Each lead receives a confidence score and a plain-language list of confirmed and unconfirmed facts.
- Below-threshold leads go to review and never proceed automatically.
- Guideline acceptance target: manually inspect 100 leads and confirm at least 90% of facts marked “verified” are correct. Do not claim this result until a real audit has been run.

### Research and personalization

Capture relevant evidence about:
- What the company does, customers, size, location, tools/technology where publicly observable.
- Recent announcements, launches, awards, press, and funding if found.
- Hiring signals and the work the company may be building.
- Decision-maker role/background/public business posts where accessible through permitted sources.
- Possible business pain points, clearly labeled as hypotheses with evidence.
- Relevant connection points.

Rules:
- Use public, business-relevant information only.
- Every personalized claim must have a source.
- Never invent facts or personal details.
- If no reliable personal detail is found, use a company-level opening.
- Avoid sensitive/intrusive details such as family information or home addresses.
- Human approval is required before a message is released.

### Workflow stages

The guideline’s stages are Find → Enrich → Verify → Research → Approve → Outreach → Track → Hand over.

Each stage must:
- Be visible in the interface/logs.
- Support pause and retry.
- Keep rules and limits in settings, not buried in code.
- Stop safely on failure; never skip ahead with incomplete or guessed data.
- Show the state of every lead in one place.

### Channels and safety

- Initial prototype is dry-run only: no real messages.
- LinkedIn/social actions are human-operated; do not automate platform activity.
- SMS is a stub/queued preview until consent and the correct registered messaging setup exist.
- Shared DNC checks must run before every proposed send and follow-up.
- A reply, bounce, or opt-out must stop the relevant sequence.
- Email compliance checks, sender identity, real business address, opt-out, domain authentication, and sending limits must be addressed before any real email campaign.
- Log every action and rule check.
- Legal review is required before production outreach.

### Caller dashboard

The caller should see:
- Who the company/decision maker is and why it is ready for a call.
- Phone and local time only when supported by reliable data.
- Engagement timeline by channel.
- Company summary, size, tools, and likely problems.
- News/funding and hiring signals with links.
- Connection points, suggested opening, and two suggested questions.
- DNC/consent/safety status.
- Call outcome buttons and notes saved to the record.
- Sources and uncertainty visible from every relevant panel.

---

## 3. Product design: what makes this feel like a real product

Avoid building only a table of leads plus a “Generate with AI” button. The product should have a coherent workbench.

### 3.1 Main navigation

1. **Overview** — campaign status, lead counts by stage, source health, review queue, recent failures, and estimated cost.
2. **Campaigns** — create/edit target settings and compare campaigns.
3. **Lead Discovery** — source controls, search terms, source-by-source results, and run history.
4. **Lead Workspace** — list/table with search, filters, confidence, stage, source count, and next action.
5. **Lead Detail** — company profile, people, evidence drawer, verification results, research, and activity history.
6. **Review Queue** — low-confidence facts, duplicates, uncertain matches, and message approvals.
7. **Outreach Preview** — proposed channel drafts and dry-run safety decision; sending disabled.
8. **Caller Briefing** — focused pre-call page and call outcome logging.
9. **Workflow Runs** — stage-by-stage logs, retries, pause/resume, and failure reasons.
10. **Settings** — source keys/status, target defaults, scoring thresholds, DNC, retention, and integration status.

For a two-day prototype, some pages can be tabs within one app. They still need real behavior, not decorative navigation.

### 3.2 Differentiating features to prioritize

**A. Evidence-first lead record**
- Every claim stores its source URL, source type, retrieval time, and short supporting text.
- Each fact has a status: `unverified`, `supported`, `verified`, `conflicting`, or `stale`.
- Clicking a fact opens the source.
- A source badge alone is not enough: show which exact fact the source supports.

**B. Explainable qualification**
- Show why the company matched or failed each campaign rule.
- Example: “Sector matches: software company; location matches: US; employee range unknown; moved to review.”
- Unknown must not be treated as a match.
- Keep qualification score separate from factual confidence. A company may fit the target but still have weak evidence.

**C. Conflict-aware verification**
- If two sources disagree on employee count, location, or company identity, show both values and dates.
- Do not silently select whichever value the AI prefers.
- Let a reviewer select a value or leave it unresolved.

**D. Safe-stop workflow**
- A lead cannot advance to message approval unless required checks pass.
- A DNC match, missing evidence, failed source check, or unresolved high-impact conflict blocks progression.
- The UI states the reason and the next useful action.

**E. Source health and provenance**
- Show each connector’s last successful run, records found, failures, and rate-limit status.
- Distinguish “source returned no results” from “source was unavailable.”
- This prevents a broken API from looking like an empty market.

**F. Honest AI research**
- AI receives retrieved evidence, not just a company name.
- It returns structured claims with evidence references, uncertainty, and a fallback.
- If evidence is insufficient, it says so and drafts a company-level opening or no draft.
- Never let an LLM fabricate a URL, job post, funding round, person, title, or email.

**G. Dry-run safety report**
- Each proposed message shows `WOULD PASS` or `BLOCKED`, with the checks performed.
- A prominent system-level indicator says “Dry run — no messages sent.”
- No send button should be active in the initial build; this is a backend rule, not merely a hidden UI control.

**H. Demo-ready workflow replay**
- Let the user open a run and see: source results → merged company → evidence checks → qualification → research → draft → approval → dry-run decision.
- This makes the engineering visible and easier to evaluate than a polished but opaque AI output.

---

## 4. Recommended architecture

Keep the architecture understandable and reliable. Use one shared database and a common record format for all sources.

### Confirmed stack (decided; do not substitute without owner approval)

| Area | Decision | Why |
|---|---|---|
| Frontend | **React + TypeScript + Vite** standalone web app in `frontend/` | Real application shell, routing, reusable components, testable UI logic |
| Backend | **Python + FastAPI** in `backend/` | Straightforward API, typed request/response models, testable logic |
| Orchestration | **LangGraph** (Python library, in-process) | Owns workflow state, nodes, conditional routing, and inspectable transition history |
| Database | **SQLite + SQLAlchemy** for the prototype | Zero setup friction; schema is written so PostgreSQL can replace it later |
| Python env | **Project-local `.venv`** in `backend/.venv` | Isolated, reproducible dependencies; never rely on a global interpreter |
| Styling | **Tailwind CSS** if it installs and configures reliably; otherwise organized CSS modules / a single clean global design system | Do not spend milestone time debugging styling infrastructure |
| UI components | One consistent, accessible component system (shadcn/ui or equivalent) **only if setup is straightforward**; otherwise a small set of our own primitives | No multiple overlapping UI libraries |
| AI | **No AI provider in Milestone 1.** A provider interface is added when research/drafting is implemented | AI is for summaries/drafts, not source-of-truth facts |
| HTTP | `httpx` with timeouts and bounded retries | Common way to call APIs and fetch permitted public pages |
| Validation | Pydantic models + deterministic rule functions | Reject malformed or incomplete records before they progress |
| Tests | Backend: **`pytest`** with fixture responses and mocked external services. Frontend: a lightweight runner (Vitest) for component/API-logic tests | Tests remain repeatable when APIs are offline or quotas run out |
| Secrets | `.env` at repo root, excluded from Git; **all secrets stay on the backend** | Prevent API keys leaking into code, repository, or browser bundle |
| Logs | Structured event rows in `workflow_runs` / `stage_events` | Every run and failure is inspectable from the UI |

**Prohibited in this project (explicitly decided by the owner):**
- **n8n** — do not install, configure, or use it as part of this product.
- **A separate custom Python stage-runner/orchestration engine** — LangGraph owns workflow transitions. Ordinary Python functions implement the individual tasks (retrieval, normalization, checks); they do not decide what happens next.
- **PostgreSQL, Docker, Redis, Celery, or extra frameworks in Milestone 1** unless a demonstrated requirement justifies them.

### Frontend/backend boundary

```text
Browser (React + TS + Vite, dev server on :5173)
   |  HTTP/JSON only — fetch() to a single typed API client
   |  no secrets, no database access, no direct provider calls
   v
FastAPI (:8000)  — REST endpoints, Pydantic request/response models, CORS limited
   |                   to the local dev origin
   |-- SQLAlchemy repositories (read/write SQLite)
   |-- LangGraph workflow invocation (runs inside the backend process)
   |-- dry-run safety guard (backend-only enforcement)
   v
SQLite file (backend/)  — single source of truth
```

Rules for the boundary:
1. React talks to FastAPI through one typed client module; no `fetch` calls are scattered through components.
2. The frontend never holds API keys, provider credentials, or database paths.
3. The frontend renders state the backend reports. It never computes qualification, confidence, or safety decisions.
4. Every mutating action (create campaign, start run, record a review decision) is a real POST/PUT to FastAPI, not local component state.
5. Local development CORS allows only the Vite dev origin (`http://127.0.0.1:5173` / `http://localhost:5173`).

### Core data flow — the agreed hybrid approach

**The five connectors do not all perform the same job.** Discovery connectors find multiple candidate companies. Enrichment connectors then investigate those discovered companies. A source can contribute to more than one job when its data supports it, but the workflow responsibilities remain explicit.

```text
Campaign settings (industry, country, size, target count, exclusions)
      |
      v
DISCOVERY: web search + suitable business directories/datasets
      |  each discovery source can return many candidate companies
      v
Normalize candidates -> merge duplicates -> one company record per company
      |
      v
ENRICH: official company website + public job postings + news/funding
      |  these sources investigate the discovered company records
      |  a source may return no relevant result or be unsupported
      v
Store every result as dated evidence linked to the company and fact
      |
      v
QUALIFY + VERIFY: target fit, evidence confidence, conflicts, exclusions/DNC
      |
      +---- insufficient/conflicting evidence ---> Human review queue
      |
      v
RESEARCH from retrieved evidence (AI summarizes; does not invent)
      |
      v
Draft message + suggested questions -> human approval
      |
      v
Dry-run safety gate (initial prototype: always no-send)
      |
      v
Caller briefing + manually logged call/activity outcomes
```

**Important:** “Find 50 leads” means keep collecting candidates from enabled discovery sources, deduplicate them, then qualify them. Do not promise 50 qualified leads if the available sources only produce fewer. Enrichment sources do not need to independently discover new companies; they primarily add evidence to the existing company records. A failed or unsupported enrichment source must be labeled accurately and must not be treated as evidence that a company has no jobs, news, or other signals.

### Important engineering separation

- **Connectors** retrieve source data.
- **Normalization** turns different source formats into one common format.
- **Verification rules** decide what is actually supported.
- **AI** summarizes evidence and drafts language.
- **LangGraph workflow** owns state, transitions, conditional routing, and the run history; it calls plain Python task functions.
- **API layer (FastAPI)** exposes state and commands to the frontend.
- **UI (React)** displays state and lets the human review it.

Do not put all of these responsibilities in one huge function or one LLM prompt.

### The agreed hybrid discovery/enrichment workflow (summary)

1. **Discovery sources** (web search; optionally a business directory/open dataset) run against the campaign settings and return **many candidate companies**.
2. **Normalize and merge duplicates** by domain and cautious identity matching into **one company record per real company**, keeping the evidence from every source that found it.
3. **Enrichment sources** (official website, public job postings, news/funding) then investigate **those already-discovered companies** — they do not run a separate market-wide search.
4. **Business directories/datasets** may add candidates to the same pool *and/or* corroborate identity facts for existing records.
5. **Qualify and verify:** target fit, evidence confidence, and safety status stay three separate things; unknown and conflicting facts stay unknown/conflicting.
6. **Human review:** anything uncertain, conflicting, or below threshold enters the review queue and never advances automatically.
7. **Research and draft** from retrieved evidence only, then **human approval**, then the **dry-run safety gate (always no-send)**, then the **caller briefing**.

---

## 5. The five source integrations — researched plan

The phrase “five sources” means five source types/connectors, not five guaranteed free databases. The agreed design is a **hybrid discovery-and-enrichment workflow**:

- **Discovery sources** find multiple candidate companies that may fit a campaign.
- **Enrichment sources** investigate companies already discovered and attach evidence to their existing records.
- Results from all sources are saved in a shared evidence model, and duplicate companies are merged rather than counted repeatedly.
- Source roles are defaults, not rigid limits: a business directory may discover a company and also support selected identity facts; a company website may confirm identity and provide enrichment evidence.

| Source | Primary role | How it is used |
|---|---|---|
| 1. Web search API | Discovery | Finds multiple candidate companies from campaign-specific queries. |
| 2. Official company websites | Enrichment and primary evidence | Investigates each discovered company’s identity, products/services, location, and public pages. |
| 3. Public job postings | Enrichment and hiring signals | Looks for published roles for discovered companies where a supported public job board exists. |
| 4. News and funding | Enrichment and timely signals | Searches for relevant articles and announcements about discovered companies. |
| 5. Business listings/registries/open datasets | Discovery and corroboration | Can discover additional candidates and/or support selected identity/legal facts, depending on actual coverage. |

Do not assume all five sources search the whole market independently. The workflow should first create a candidate pool, then enrich that pool. Keep the connector interface consistent so each connector can be tested independently.

### Source 1 — Web search API: discover candidate companies

**Role: DISCOVERY.** Find multiple companies that might fit the campaign, using targeted searches such as US B2B software companies, IT services firms, or companies in a selected sub-sector. A result is a candidate, not a verified lead.

**Recommended first provider:** Brave Search API, because its official pricing page currently lists web search at $5 per 1,000 requests and $5 monthly credits. Confirm signup, actual account access, and current terms before coding around it.  
Official docs/pricing: https://api-dashboard.search.brave.com/documentation/pricing  
Overview: https://brave.com/search/api/

**Implementation**
1. Build search queries from campaign sector, country, and other criteria.
2. Retrieve result title, URL, snippet, and source metadata.
3. Keep the original result as a candidate, not a verified lead.
4. Extract likely company domain from the result URL.
5. Deduplicate by normalized domain and later by legal/company identity.
6. Store query, source URL, retrieval timestamp, and provider response metadata.
7. Send company URLs to the website connector for deeper evidence.

**Test before moving on**
- One query returns structured records.
- Each record has a usable URL and provenance.
- Repeated results merge instead of creating duplicate companies.
- API timeout/quota failure appears as a source error, not “zero leads.”

**Risks and fixes**
- Search snippets are incomplete or stale: treat them only as discovery evidence.
- Search engines may return directories, articles, or similarly named companies: resolve the actual company website before qualification.
- API usage can cost money: cache queries/results and enforce a per-campaign request limit.
- Do not depend on Google Custom Search JSON API for a new integration: official docs say it is closed to new customers, with existing users scheduled to transition by January 1, 2027. See https://developers.google.com/custom-search/v1/overview.

### Source 2 — Company websites: enrich discovered companies with primary evidence

**Role: ENRICHMENT.** For each discovered company with a usable official domain, verify what the company does and collect public business facts and technology/hiring signals actually published on its website. This connector should normally receive company records/domains from the discovery stage; it is not expected to run a separate market-wide company search.

**Implementation**
1. Fetch the company homepage and likely pages such as About, Products/Services, Careers, Contact, and public news pages.
2. Respect the site’s access rules, crawl directives, rate limits, and terms; do not bypass logins or access controls.
3. Use conservative timeouts, a small page limit per domain, and caching.
4. Extract title, headings, relevant text, canonical URL, page date when available, and retrieval timestamp.
5. Store a short evidence excerpt and the exact page URL for every extracted fact.
6. Detect links to public job boards or press/news pages and pass them to the relevant connectors.

**Test before moving on**
- A known company’s official website is fetched and the company description can be traced to a page.
- Blocked/timeout/robots-denied sites are recorded cleanly.
- The app never claims a missing page proves a fact is false.

**Risks and fixes**
- Website HTML changes: isolate extraction logic and add fixtures for tests.
- Sites block bots or render content in JavaScript: mark as unavailable; do not build a browser-bypass scraper for the prototype.
- Company websites rarely publish exact employee counts or current decision-maker details: use other permitted sources or mark unknown.
- The Robots Exclusion Protocol is documented in RFC 9309, but robots.txt is not a substitute for reviewing terms and applicable law: https://www.rfc-editor.org/rfc/rfc9309.html.

### Source 3 — Public job postings: enrich discovered companies with hiring signals

**Role: ENRICHMENT.** For each discovered company where a supported public job board can be identified, use real open roles to show what it is hiring for and what it may be building. Hiring is a signal, not proof of a business problem. This source is not a universal company-discovery engine.

**Recommended implementation path:** Greenhouse public Job Board API for companies whose public career pages expose a Greenhouse board. Its public GET endpoints do not require authentication, according to the official documentation. The board token is company-specific, so this is not a universal search API.  
Official docs: https://docs.greenhouse.io/job-board

**Implementation**
1. Discover the company’s careers page or a Greenhouse board URL.
2. When a Greenhouse board token is available, request published jobs and, where useful, full job descriptions.
3. Save job title, location, department, posted/updated date if supplied, job URL, and relevant excerpt.
4. Link each job to the company record with evidence.
5. Identify signals with simple transparent rules first (e.g. repeated hiring in data engineering); AI may summarize what the job description says, but must label inferred needs as hypotheses.
6. Add a provider interface for other public job-board systems later; do not promise universal job coverage in version one.

**Test before moving on**
- A known Greenhouse board returns current public jobs.
- Job URLs open the source post.
- No-job-found is distinguished from unsupported board type or provider error.
- Hiring signals link back to the exact job description.

**Risks and fixes**
- Not all companies use Greenhouse: report coverage honestly and add other sources only after this connector is tested.
- Job posts can be stale or removed: store retrieval time and the source’s date when available.
- Job requirements do not prove the company has a particular pain point: present “possible signal” with evidence, not as a fact.

### Source 4 — News and funding: enrich discovered companies with recent events

**Role: ENRICHMENT.** Search for launches, announcements, acquisitions, funding, and other recent events about each discovered company. These signals can support timely, specific outreach. Do not treat an empty search as proof that no event occurred.

**Recommended prototype provider:** GNews API is one option with documented search endpoints. Its official pricing currently lists a free development/testing tier of 100 requests/day and up to 10 articles per request, but with a 12-hour delay and non-commercial restrictions; paid plans are listed for commercial/public use. Do not assume the free plan is appropriate for a commercial pilot.  
Official docs: https://docs.gnews.io/  
Pricing/terms: https://gnews.io/pricing

**Implementation**
1. Search by exact company name plus domain/name variants.
2. Use date range and query operators where supported.
3. Store article title, publisher, URL, publication date, and relevant excerpt.
4. Check whether the article is actually about the target company, not a different company with the same name.
5. Prefer original company announcements, reputable publishers, and direct sources when available.
6. Mark old news as old; do not present it as “recent.”
7. Funding should be “not found” unless supported by evidence. Avoid inventing funding status.

**Test before moving on**
- Search returns articles with working URLs and dates.
- Same article is not duplicated repeatedly.
- Similar-name false matches are rejected or sent to review.
- An empty result is not described as proof that the company has never raised funding.

**Risks and fixes**
- Provider’s free tier may not permit commercial use: check current terms before use; use it only for permitted development/testing if appropriate.
- News APIs can omit articles, have delays, or return thin metadata: show source coverage and retrieval dates.
- Funding and company news are often behind paywalls: use only accessible metadata/excerpts and do not circumvent paywalls.

### Source 5 — Public business listings and open datasets: additional discovery and selected corroboration

**Role: DISCOVERY + CORROBORATION, depending on provider coverage.** This source may find additional candidate companies, and/or support selected identity or legal facts for companies already discovered. It should feed the same candidate pool and shared company records—not create a separate disconnected list. This category is broad. There is no single universally complete free database for private US technology companies, current headcount, decision makers, and contact details.

**Recommended starting strategy**
- Use public/open government or corporate registry data where it actually covers the company and fact.
- Use SEC EDGAR APIs as a supplemental source for companies that file with the SEC; it is not a directory of all private small businesses.
- Treat OpenCorporates or other commercial directories as optional integrations only after checking access, quota, license, and reuse terms.
- Do not make Google Places the core source unless a business-listing use case justifies its cost and data terms; its API has per-SKU billing and field-mask considerations.

Official references:
- SEC developer resources: https://www.sec.gov/about/developer-resources
- SEC data APIs: https://data.sec.gov/
- OpenCorporates self-serve API terms (check current access and terms): https://opencorporates.com/legal-information/self-service-api-terms-of-service/
- Google Maps Platform pricing: https://developers.google.com/maps/billing-and-pricing/pricing

**Implementation**
1. Start with a small adapter interface that can accept structured business/registry records.
2. If the provider can discover companies, add its records to the shared candidate pool; if it can corroborate an existing company, attach the record to that company.
3. Match on domain, normalized name, location, and identifiers where available.
4. Save the source and the exact fields it supports.
5. Never use a registry filing as evidence for unrelated fields such as current employee count or current executive title.
6. If no suitable free source can legally provide a field, leave it unknown rather than manufacturing a value.

**Test before moving on**
- At least one supported provider/dataset returns records and source links.
- Matching does not merge two different companies just because their names are similar.
- Unsupported coverage is clearly labeled.
- Provider quota/terms failures are visible.

**Risks and fixes**
- Registry data may be incomplete, stale, or only cover certain legal entities: use it for identity/legal facts it supports.
- Provider terms can restrict storage, redistribution, or commercial use: document the decision before integration.
- Private-company headcount is especially difficult to verify independently: keep ranges and sources, and use `unknown` when the evidence is weak.
- Do not describe these five sources as guaranteeing every requested field. Their job is to provide complementary evidence.

### Connector interface — required for all five

Each connector must declare its role (`discovery`, `enrichment`, or `both`) and return a standard result format. The **LangGraph workflow**—not the connector itself, and not a hand-rolled stage runner—decides when it runs:

1. Run enabled discovery connectors and collect candidate records.
2. Normalize domains/names and merge duplicates into one company record per company.
3. Run enrichment connectors against the resulting company pool, using the company domain/name or supported board identifiers.
4. Attach every source result to the matching company and specific facts it supports.
5. Run qualification and verification only after the configured discovery/enrichment attempts have completed or been explicitly marked unavailable.

A connector returning zero results is different from a connector failing. Store `success_with_results`, `success_empty`, `unsupported`, `not_configured`, and `failed` (or equivalent) states separately.


Every connector should return the same shape, for example:

```json
{
  "source_type": "web_search",
  "provider": "brave",
  "external_id": null,
  "company_name_candidate": "Example Software",
  "website_url": "https://example.com",
  "record_url": "https://example.com/about",
  "retrieved_at": "2026-10-20T10:00:00Z",
  "fields": {
    "description": {
      "value": "Builds software for ...",
      "evidence_url": "https://example.com/about",
      "evidence_excerpt": "..."
    }
  },
  "status": "success",
  "warnings": []
}
```

This is a schema example, not a real lead. Actual records must come from the connected source.

All connectors need:
- `search()` or `fetch()` method appropriate to their source.
- Timeout and bounded retry behavior.
- Rate limiting and caching.
- Structured error status.
- Provider attribution and retrieval timestamp.
- Tests with mocked responses.
- No API keys exposed to the frontend.

---

## 6. Shared data model

Start with a small but intentional database schema. The same company should not become five separate leads because five sources found it.

### Core tables

**campaigns**
- `id`, `name`, `created_at`, `status`
- `settings_json` (sector, countries, employee range, titles, exclusion rules, confidence threshold)
- `settings_version` or immutable settings snapshot

**companies**
- `id`, `canonical_name`, `normalized_name`, `website_domain`, `country`, `location`
- `sector`, `employee_min`, `employee_max`, `phone_system`
- `workflow_status`, `qualification_score`, `confidence_score`
- `created_at`, `updated_at`

**people**
- `id`, `company_id`, `full_name`, `title_as_found`, `profile_url`
- `work_email`, `phone` (nullable; only when obtained from permitted sources)
- `verification_status`, `last_checked_at`

**source_records**
- `id`, `company_id`, `person_id` (nullable), `source_type`, `provider`
- `source_url`, `retrieved_at`, `published_at`
- `raw_payload_json`, `content_hash`, `status`, `error_message`

**facts**
- `id`, `company_id`, `person_id` (nullable), `field_name`, `field_value`
- `status`, `confidence`, `verified_at`, `reviewer_id` (nullable)

**fact_evidence**
- `id`, `fact_id`, `source_record_id`, `evidence_excerpt`, `supports_or_conflicts`
- Keep multiple evidence items for one fact.

**research_profiles**
- `company_id`, `summary`, `likely_pain_points_json`, `connection_points_json`
- `generated_at`, `model_name`, `prompt_version`, `status`

**message_drafts**
- `id`, `company_id`, `person_id`, `channel`, `subject`, `body`
- `evidence_fact_ids_json`, `status`, `approved_by`, `approved_at`
- Drafts are not sends.

**workflow_runs / stage_events**
- `run_id`, `campaign_id`, `company_id`, `stage`, `status`, `attempt`
- `started_at`, `finished_at`, `error_code`, `error_message`, `details_json`

**suppression_list**
- Normalized email/domain/phone/person identifier as applicable, reason, source, created_at, scope.
- One shared suppression policy across channels.

**outreach_events**
- `id`, `company_id`, `person_id`, `channel`, `event_type`, `occurred_at`, `metadata_json`
- In prototype, event types include `draft_created`, `approved`, `dry_run_passed`, `dry_run_blocked`, `reply_logged`, `call_outcome_logged`; do not invent send/open/click events.

**call_notes**
- `id`, `company_id`, `person_id`, `outcome`, `notes`, `created_at`, `created_by`.

For a two-day demo, the implementation can simplify this schema, but source evidence, workflow events, suppression status, and message approval must not be dropped.

---

## 7. Qualification, confidence, and verification rules

Do not ask an LLM to make all safety decisions. Use explicit code rules.

### Keep three concepts separate

1. **Target fit:** Does the company match campaign requirements?
2. **Evidence confidence:** How well are the facts supported?
3. **Safety status:** Is it permitted to proceed to the next stage?

A lead may have strong target fit but poor evidence. A lead may be well researched but blocked by DNC. These must not collapse into one score.

### Proposed first-pass rule

For each required campaign condition:
- `pass`: evidence supports the rule.
- `fail`: evidence supports that it does not match.
- `unknown`: not enough evidence.
- `conflict`: sources disagree.

Decision:
- **Qualified:** all required conditions pass and minimum evidence checks pass.
- **Review required:** one or more important fields are unknown/conflicting or confidence is below the configured threshold.
- **Rejected:** a required condition clearly fails.
- **Blocked:** DNC/suppression or another safety rule applies.

Do not invent numerical weights before testing. Begin with a transparent rule list and calibrate any score using a manually reviewed sample.

### Verification standards

- A fact is “verified” only when the defined evidence requirement is met.
- Two URLs are not automatically two independent sources if both repeat the same press release or syndicated text.
- For important facts, store both sources and whether they independently support the fact.
- Email syntax/domain checks are not proof that a mailbox exists.
- A third-party “deliverable” result is a provider estimate, not a guarantee.
- Never send an email to test mailbox existence.
- Employee count may be a range or unknown; do not present estimates as exact counts.
- Keep the original title exactly as found, alongside any normalized title used for matching.
- Store “checked at” dates; old evidence may become stale.

### Manual accuracy audit

Create an audit screen/export for a reviewer to inspect a sample:
- Which facts were marked verified?
- Which sources support them?
- Is each fact actually correct?
- Was the evidence current and about the right company?
- Record correct/incorrect/uncertain and reason.
- Report verified-fact accuracy as `correct verified facts / all manually reviewed verified facts`.
- Report sample size and sampling method. Do not claim the 90% guideline target based on a handful of demo records.

---

## 8. Research and AI implementation

### What AI should do

- Summarize retrieved pages and job descriptions.
- Suggest likely business-relevant opportunities, labeled as hypotheses.
- Draft a short opening and two questions.
- Explain a lead’s evidence in plain language.
- Produce structured output that the backend validates.

### What AI must not do

- Discover facts from model memory and present them as sourced.
- Make up employees, job posts, funding, emails, phone numbers, technologies, or public posts.
- Mark a fact “verified” by itself.
- override DNC, consent, country restrictions, or approval.
- Turn a weak signal into a confident claim.

### Suggested structured output

```json
{
  "company_summary": {
    "text": "...",
    "evidence_ids": ["fact-or-source-id"]
  },
  "signals": [
    {
      "claim": "...",
      "type": "observed_fact_or_hypothesis",
      "evidence_ids": ["source-id"],
      "confidence": "high_medium_low"
    }
  ],
  "opening": {
    "text": "...",
    "evidence_ids": ["source-id"],
    "fallback_used": false
  },
  "suggested_questions": ["...", "..."],
  "limitations": ["..."]
}
```

Validate this output with Pydantic. If an evidence ID does not exist in the provided evidence set, reject the claim or require regeneration. Render evidence links from the database, not from URLs invented by the model.

### Cost and reliability

- Put model selection behind a small interface so providers can be swapped.
- Use API-based models since local GPU is unavailable; this does not require running a large model on the laptop.
- Send only relevant excerpts, not whole websites.
- Cache research results by company/content hash and prompt version.
- Log model name, token usage/cost where available, duration, and error.
- If the model fails, preserve source records and use a safe company-level fallback or mark research pending.
- Do not rotate API keys to evade a provider’s quota or billing rules.
- Keep deterministic checks outside the model.

---

## 9. Workflow orchestration and failure handling

**Decided: LangGraph owns the workflow.** A LangGraph `StateGraph` running inside the FastAPI backend process defines the state, the nodes, the conditional edges, and the recorded transition history. Individual nodes are ordinary Python functions (retrieval, normalization, checks, scoring) that receive and return state.

**Explicitly prohibited:**
- **n8n** — not installed, not configured, not used, even if it happens to exist on the machine.
- **A separate custom Python stage runner / orchestration engine.** Business logic stays in tested Python functions, but *the decision about what happens next* belongs to the LangGraph graph, not to a hand-rolled runner class.

Because the graph runs in-process, business-critical checks still live in ordinary tested functions, and every node still writes to the database-backed event log. Do not spend the first day debugging orchestration infrastructure.

### Milestone 1 graph (smallest real graph)

State carries: `campaign_id`, `company_id` (a clearly labeled test record), `stage`, `findings`, `review_reason`, `error`, `outcome`.

Nodes: `start` → `find` → `merge` → `evaluate` → router → (`needs_review` | `failed` | `end`).

Initial outcomes the graph must produce honestly:
- `continue` — stage completed, next stage runs.
- `needs_human_review` — an unknown/conflicting/low-confidence condition held the record; the reason is stored in the event log.
- `stopped_after_error` — a task raised; the run stops, the error is stored, and the record does **not** advance.

Every node writes a `stage_events` row (`stage`, `status`, `started_at`, `finished_at`, `error_message`, `details_json`).

### State machine

States used by the product (the Milestone 1 graph only exercises the first few):
- `discovered`
- `enriching`
- `needs_review`
- `qualified`
- `researching`
- `draft_ready`
- `awaiting_approval`
- `approved_for_dry_run`
- `dry_run_passed`
- `blocked`
- `failed_retryable`
- `failed_permanent`
- `call_ready`
- `closed`

Every transition must be explicit. A failed stage must not silently advance the lead.

### Retries

- Retry transient timeouts, rate limits, and server errors with a small maximum attempt count and backoff.
- Do not endlessly retry invalid API keys, malformed input, or policy-denied access.
- Store each attempt, error code, and timestamp.
- Add a “retry” action for failed records and a “pause campaign” control.
- Use idempotency: repeating a stage should not create duplicate companies, drafts, or events.
- Do not repeat irreversible actions automatically. The prototype has no real send action, but the rule matters for future sending.

### Distinguish empty results from failures

- `success_empty`: provider responded successfully with no matching records.
- `success_with_results`: results returned.
- `partial`: some pages/results worked, others failed.
- `rate_limited`, `timeout`, `auth_error`, `policy_blocked`, `parse_error`, `provider_error`.
- Display these separately in the UI.

---

## 10. Product screens and expected behavior

### Frontend design requirements (owner-decided, high priority)

The interface must look like a thoughtfully designed, modern B2B SaaS application, not a generic AI-generated dashboard.

Visual direction:
- White or light neutral surfaces; dark, readable typography.
- One restrained accent color; subtle borders; carefully controlled shadows.
- Consistent spacing, alignment, typography, and component sizes; clear hierarchy and purposeful whitespace.
- Responsive for typical laptop screens; accessible contrast, visible focus states, usable form controls.

Avoid:
- Excessive cards, badges, gradients, shadows, decorative icons.
- Giant headings, oversized metrics, random charts, fabricated analytics.
- Emoji used as interface icons; inconsistent spacing; arbitrary colors.
- Crowded tables, long unstructured pages, unnecessary visual elements.
- A dashboard that looks like a collection of unrelated templates.

Application shell:
- Restrained left sidebar for primary navigation.
- Clean top bar showing the current section and relevant actions.
- Well-structured main content area.
- Reusable components for buttons, form controls, tables, status indicators, empty states, and page headers.

Screens to prioritize for Milestone 1:
1. **Overview** — campaign summary, real database-backed counts, recent workflow activity, next actions.
2. **Campaigns** — campaign list and a clean create-campaign form.
3. **Workflow runs** — stage progression, status, timestamps, errors.
4. **Run details** — readable event history and reasons for review or failure.

Do not build empty screens for every future feature just to make the sidebar look complete. Label future capabilities as unavailable only when their presence is genuinely useful.

A persistent banner must be visible in the shell: **`DRY RUN — NO MESSAGES SENT`**.

Design quality process:
- Use consistent design tokens and small reusable components; keep styling organized so a separate agent can refine visuals without touching backend logic.
- All displayed metrics come from real API responses, with honest loading, empty, success, and error states.
- Test data must be visibly distinguished from real retrieved data.
- Do not claim the UI "looks polished" unless it has actually been inspected in a browser. Report build results and the URLs to inspect instead.

### Overview
- Total discovered, qualified, review-required, rejected, and blocked.
- Leads by source and workflow stage.
- Latest workflow failures and retry action.
- Cost/request counts where known.
- “Dry run only” status.

### Campaign setup
- Editable sector/sub-sector, country, employee range, titles, exclusions, and minimum evidence threshold.
- Validate the configuration before running.
- Save an immutable settings snapshot with each campaign/run.

### Discovery and enrichment
- “Run discovery” runs enabled discovery sources (web search and any configured business-listing/registry source that supports candidate discovery).
- Discovery sources may each return many candidates. Normalize and merge candidates into one company record before enrichment.
- “Enrich discovered companies” runs website, job-posting, and news/funding lookups for the selected company pool.
- Allow “Run source” individually for debugging and “Run campaign workflow” for the normal end-to-end path.
- Display provider status, query, number of candidates/records found, number of new companies added, duplicate count, elapsed time, errors, and cost where known.
- Let a reviewer inspect raw source results before treating them as leads. Never imply an enrichment source independently discovered the whole market.

### Lead table
- Company/domain, country, sector, employee range or unknown, source count, evidence confidence, target fit, workflow state, next action.
- Filters for source, stage, score, country, and review status.
- Search and duplicate grouping.
- Export CSV only if it preserves evidence links/status and does not expose unnecessary personal data.

### Lead detail
Tabs or panels:
1. Overview and qualification explanation.
2. Facts and evidence.
3. Sources and raw results.
4. Hiring/news research.
5. People (only evidence-backed public business details).
6. Message drafts and approval.
7. Workflow/activity history.
8. Call notes.

### Review queue
- Show the specific uncertainty, conflicting values, source evidence, and a clear action: accept value, reject, keep unknown, merge, or retry.
- Review decisions are logged with reviewer and timestamp.

### Outreach preview
- Show channel, draft, evidence used, missing information, safety checks, and exact dry-run outcome.
- Every channel remains non-sending in the prototype.
- DNC and missing approval should produce a visible blocked state, not just a warning.

### Caller briefing
- A focused single-company screen, not another generic AI chat.
- Show who/why now, source-backed summary, current signals, two suggested questions, safety state, and notes/outcome buttons.
- Never show a fabricated phone number or claim engagement happened if no real outreach provider was connected.

---

## 11. Outreach, CRM, and compliance boundary

### Prototype behavior

Build drafts, safety checks, event tracking structures, and simulated outcomes. **Do not send real email, SMS, LinkedIn messages, social messages, or website-form submissions.** Do not manufacture opens, clicks, replies, or bounces.

The initial demo can record a human-entered reply or call outcome as a manual event. Label it as manually logged.

### Future controlled pilot

Before enabling real email:
- Confirm sender identity and physical business address.
- Set up SPF, DKIM, and DMARC for the chosen sending domain(s).
- Verify consent/legal basis and recipient eligibility with qualified advice.
- Provide a working opt-out and shared suppression list.
- Stop follow-ups on reply, bounce, or opt-out.
- Set low sending limits, monitor bounce/complaint rates, and use a dedicated sending domain as appropriate.
- Test with internal seed addresses first.
- Release one channel at a time only after the owner approves the safety gate.

The FTC says CAN-SPAM applies to commercial email including B2B messages; its guidance covers truthful headers/subjects, postal address, opt-out, and honoring opt-outs. Official guide: https://search.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business

For LinkedIn, use human-operated drafts and links only. LinkedIn’s published guidance prohibits unauthorized scraping and automated activity: https://www.linkedin.com/help/linkedin/answer/a1341543

SMS stays disabled until consent, registration, provider setup, quiet-hour logic, and opt-out handling are confirmed. Do not treat a publicly listed phone number as SMS consent. Legal rules vary by jurisdiction; the guideline itself says a US lawyer should confirm requirements before real sending.

### CRM

The guideline says GoHighLevel is assumed but asks the founder to confirm it; this is not settled. Therefore:
- Keep an internal record as the prototype’s source of truth.
- Add a CRM adapter interface.
- Do not block the entire prototype on CRM credentials.
- Once confirmed, map company/person IDs and activity events, support sync retries, and avoid duplicate records.
- Log sync failures and make them retryable.
- Do not claim CRM integration is working until tested against a real account.

---

## 12. Implementation sequence

Implement one connector at a time, but preserve the hybrid roles. Test connectors individually during development; in a campaign run, execute discovery first, merge candidates, and then enrich those company records. Do not begin all five connectors simultaneously.

### Phase 0 / Milestone 1 — Project setup, runnable foundation

Build:
- Repository structure: `backend/` + `frontend/`, configuration, `.env.example`, dependency files, root `README.md`, `.gitignore`.
- `backend/.venv` project-local virtual environment.
- SQLite database and schema initialization (SQLAlchemy models).
- Campaign settings model.
- Shared connector **result** interface (schema and status enum only — no connectors yet).
- A small real **LangGraph** workflow: explicit state, nodes, conditional routing, honest outcomes.
- Workflow event log (`workflow_runs`, `stage_events`) and an overview endpoint.
- React + TypeScript + Vite application shell that calls the real API.
- Global dry-run/no-send guard enforced in backend code.

Done when:
- A sample campaign can be created through the React UI and is retrieved from the database.
- A clearly labeled test company moves through the initial LangGraph workflow, including the human-review and error outcomes.
- Every stage creates a visible, timestamped log entry that the UI can display.
- The React app shows loading, empty, success, and error states from real API responses.
- No send function is exposed or callable.
- `pytest` passes and the frontend production build succeeds.

### Phase 1 — Source 1: Web search discovery

Build and test the first discovery connector. It should return multiple real candidate companies, with original result URLs and timestamps. Add domain normalization and initial deduplication.

Do not proceed until repeated runs show candidates, duplicate behavior, and clear errors.

### Phase 2 — Source 2: Company website enrichment

For each discovered company with a usable domain, fetch a small, bounded set of permitted public pages. Extract company facts and evidence links. Add timeouts, caching, and blocked/unsupported statuses.

Do not proceed until evidence is clickable and website failures are handled safely.

### Phase 3 — Source 3: Job-posting enrichment

For discovered companies with public Greenhouse board tokens, store current public job posts and source URLs. Mark unsupported board types separately; do not search the entire market through this connector.

Do not proceed until a real job post is shown with a link and date where available.

### Phase 4 — Source 4: News/funding enrichment

Search for news about discovered companies. Add a provider adapter only after reviewing plan and usage terms. Add company-name/domain matching and article deduplication. Label news recency clearly.

Do not proceed until false matches and empty/error cases are covered.

### Phase 5 — Source 5: Registry/business/open dataset

Choose the provider after confirming coverage and permitted use. If it supports discovery, add its companies to the shared candidate pool; if it supports facts about existing candidates, attach that evidence to the matching company. Do not create a separate lead list or promise fields the provider does not supply.

Do not proceed until source-specific fields, role, coverage, and unsupported fields are clearly represented.

### Phase 6 — Merge, verify, score, and review

Build:
- Domain-first duplicate matching with cautious name/location fallback.
- Fact/evidence storage.
- Pass/fail/unknown/conflict statuses.
- Transparent qualification and evidence confidence.
- Review queue and reviewer decisions.
- Manual accuracy audit export.

Done when:
- Same company from multiple sources becomes one record with multiple source records.
- Conflicting facts are visible.
- Unknown data never silently becomes verified.
- DNC-blocked records cannot advance.

### Phase 7 — Research and AI drafts

Build evidence-bounded company summaries, hiring/news signal summaries, opening line, and two questions. Include evidence IDs in the model output and validate them. Add fallback behavior for no evidence or model failure.

Done when:
- Every specific claim in a draft points to retrieved evidence.
- Weak evidence triggers a company-level fallback or review.
- Model failure does not break or bypass verification.

### Phase 8 — Approval and outreach dry run

Build approval/edit/reject workflow, DNC checks, missing-data checks, dry-run result, and event logs. Make no real network send possible from the prototype.

Done when:
- Approved draft can pass a simulated safety check.
- DNC or missing approval blocks it.
- The app clearly says nothing was sent.
- A repeated run does not duplicate draft or activity records.

### Phase 9 — Caller briefing and call notes

Build a caller-ready page with facts, news, hiring, evidence links, suggested opening/questions, safety status, and call outcome/notes.

Done when:
- A user can prepare for a call from this page without searching through the rest of the app.
- Call outcome is saved to the same company record and visible in history.

### Phase 10 — Demo hardening

- Seed a campaign using real retrieved data, not fake company profiles.
- Prepare one high-confidence company, one review-needed company, one duplicate candidate, one source failure, and one DNC-blocked test record. Test fixtures can be synthetic but must be clearly marked as test data.
- Add loading/empty/error states.
- Test API key missing, provider timeout, rate limit, malformed response, AI outage, and repeated stage execution.
- Write setup/run instructions and a demo script.
- Capture screenshots only from the actual running product.

---

## 13. Two-day priority plan

This is a prioritization plan, not a guarantee of the amount of work possible. It assumes one developer and a take-home deadline.

### Day 1 — Make discovery real and trustworthy

1. Set up the backend, database, configuration, and basic interface.
2. Implement Source 1 as the first discovery connector and test it independently.
3. Store candidate records, provenance, and timestamps from the start.
4. Add company normalization and basic duplicate handling.
5. Implement Source 2 to enrich discovered domains with primary website evidence.
6. Add a first useful lead table and lead detail/evidence view.
7. Keep a working checkpoint and a demoable build.

**Day 1 target:** A user runs a campaign and sees real candidate companies with source links; opening a company shows facts from its real website. Failures are visible.

### Day 2 — Turn it into a differentiated workflow

1. Implement Source 5 as an additional discovery/corroboration source only if its coverage and terms are clear and time remains; merge any new candidates into the same company pool.
2. Implement Source 3 (job posts) to enrich discovered companies where supported.
3. Implement Source 4 (news) to enrich discovered companies if time and provider access allow.
4. If time is tight, leave unsupported sources clearly marked as unconfigured rather than faking results.
4. Add transparent qualification, confidence, and review queue.
5. Add evidence-based AI summary/draft with strict validation.
6. Add approval and always-dry-run safety checks.
7. Add a focused caller briefing and call notes.
8. Test key failure cases and rehearse the demo.

**Important:** If time becomes tight, finish the end-to-end chain for a smaller set of real companies rather than claiming five integrations work when they do not. A connector counts as complete only when its live call, error path, data mapping, and test have all been checked.

---

## 14. Test plan and acceptance gates

### Connector tests
- Valid API response.
- Empty result.
- Timeout.
- Rate limit.
- Authentication failure.
- Malformed response.
- Duplicate result.
- Source URL unavailable.
- Re-run idempotency.

### Data tests
- Same company/domain found by several sources merges correctly.
- Similar company names do not automatically merge.
- Each displayed fact links to evidence.
- Conflicting values remain visible.
- Stale data is marked.
- Unsupported fields remain unknown.

### Safety tests
- DNC match blocks every channel.
- Missing human approval blocks the draft.
- Unknown/low-confidence required fact cannot be treated as verified.
- AI output with unknown evidence IDs is rejected.
- Model/source outage never advances the lead.
- Dry-run mode cannot call any real send provider.
- No fake engagement events appear.

### Workflow tests
- Each stage records start/end/status.
- Retry limit works.
- Pause prevents new stage work.
- Retry does not duplicate companies or drafts.
- Failures can be inspected from the UI.
- Manual review action is logged.

### Product usability tests
- A user can create a campaign without editing code.
- A user can see why a lead qualifies or needs review.
- A user can open evidence links.
- A user can approve/reject/edit a draft.
- A user can produce a caller briefing and save call notes.
- Missing integrations and source outages are clearly labeled.

### Quality audit
The 90% verified-fact target from the guideline is a later measured acceptance test. Build the audit mechanism now; do not claim compliance until a suitably sized, manually reviewed sample has been scored.

---

## 15. Main risks and mitigation table

| Risk | Why it matters | Mitigation |
|---|---|---|
| Source/API unavailable or quota exhausted | Search may return nothing or the workflow may stall | Per-source status, bounded retries, caching, clear errors, continue only where safe |
| Search results are mistaken for verified companies | Bad leads damage all downstream steps | Search results are candidates; verify against official site and another independent source |
| Discovery and enrichment roles get mixed up | Workflow wastes calls or displays separate duplicate lead lists | Make discovery sources populate one shared candidate pool; run enrichment sources against those company records; show coverage and unsupported states |
| Conflicting or stale company facts | Wrong qualification and personalization | Store fact-level evidence and dates; conflict status; human review |
| Duplicate companies | Inflated lead count and repeated outreach | Normalize domain; cautious matching; preserve merged source history |
| Incorrect employee count | Campaign filters become misleading | Use supported ranges, disclose estimates, mark unknown if not corroborated |
| Decision-maker data unavailable | Personalization may be weak or incorrect | Use only permitted public business evidence; company-level fallback |
| AI hallucination | False claims in messages can damage trust | Evidence IDs, structured output, backend validation, fallback, human approval |
| Model API limits/cost | Demo may fail or become expensive | Cache, limit context, track usage, handle 429/5xx, use configurable provider |
| Scraping/site terms | Legal, privacy, and reliability risk | Prefer documented APIs; respect access rules and terms; no login/access-control bypass |
| Outreach accidentally sent | Major safety and evaluation risk | No send implementation in prototype; backend dry-run guard; no active provider credentials |
| DNC/opt-out not global | A blocked contact could be reached through another channel | Shared suppression table checked at each proposed action |
| UI looks polished but core is fake | Weak evaluation result | Demo real data, show provenance, logs, error paths, and an end-to-end run |
| Too much scope for two days | Incomplete integrations and no demo | Prioritize one working chain, source-by-source tests, explicit scope freeze |
| Orchestration over-engineered | Time lost to infrastructure instead of product logic | LangGraph only, in-process, no n8n and no hand-rolled stage runner; graph kept deliberately small |
| CRM credentials not confirmed | Integration blocks progress | Keep internal DB as source of truth; use adapter interface; label CRM sync unconfigured |
| Legal/compliance rules vary | Risk before real outreach | Dry-run only; legal review before pilot; channel-by-channel enablement |
| Demo depends on live provider uptime | Failure during evaluation | Cache prior real responses for repeatable demo, clearly label cached data and timestamp; also show live source status |
| Secrets accidentally committed | Provider account abuse | `.env`, `.gitignore`, `.env.example`, rotate leaked keys; keep keys server-side |

---

## 16. Explicit non-goals for the two-day prototype

Do not spend time on these unless the core chain is already working:
- Autonomous AI phone calls.
- Meeting booking or multi-week nurture sequences.
- Automated LinkedIn/social posting or scraping.
- Cold SMS.
- Fully automatic live email sending.
- Universal access to all job boards.
- Guaranteed private-company employee counts or decision-maker emails.
- Complex multi-agent architecture for its own sake.
- A large CRM clone.
- Production deployment, multi-tenant security, or a fully hardened team permissions model.
- Claims of 90% accuracy without the required manual audit.

These are future phases, not reasons to weaken the first end-to-end demo.

---

## 17. Demo story

Use one campaign and a small set of real retrieved companies.

1. **Create campaign:** Show editable sector, country, employee range, decision-maker titles, and exclusions.
2. **Find companies:** Run the search connector and show source status and actual result links.
3. **Open a company:** Show the official site evidence and other source records.
4. **Show a signal:** Open a real job post or news article and explain the possible business implication without presenting the inference as fact.
5. **Show verification:** Demonstrate verified vs unknown vs conflicting fields.
6. **Show a review case:** Explain why a record is held instead of being pushed through.
7. **Generate research:** Show that the AI uses evidence references and falls back when evidence is weak.
8. **Approve a draft:** Edit or reject the opening as a human.
9. **Show safety gate:** Demonstrate a DNC-blocked case and an allowed dry-run case.
10. **Show caller briefing:** Open the single-page briefing and save a call outcome.
11. **Show workflow history:** Prove the stages, retries, and decisions were logged.

Do not say “sent,” “opened,” or “replied” unless that event genuinely occurred through a connected channel or was manually entered and labeled as such.

---

## 18. Open questions to confirm with the project owner

The guideline explicitly leaves these unresolved:
- Which B2B technology sub-sectors and which services are being sold first?
- Is GoHighLevel the confirmed CRM, or should another CRM be used?
- How many leads per week should the first version handle?
- What budget is allowed for search, data, domains, and mailboxes?
- Which machine will host the system and any local models?
- Who approves drafts and who may eventually enable sending?
- Does SMS remain a stub until consent is collected?
- What is the agreed phase schedule and how will the 90% accuracy sample be reviewed?

For the take-home demo, choose sensible defaults but clearly label them as prototype defaults rather than owner-approved business policy.

---

## 19. External references checked

The following official/provider pages were reviewed while preparing this plan. Provider terms, pricing, access, and product status can change; recheck before implementation or commercial use.

1. Brave Search API pricing and features: https://api-dashboard.search.brave.com/documentation/pricing
2. Google Custom Search JSON API status/pricing notice: https://developers.google.com/custom-search/v1/overview
3. Greenhouse Job Board API documentation: https://docs.greenhouse.io/job-board
4. GNews documentation: https://docs.gnews.io/
5. GNews pricing and free-tier limitations: https://gnews.io/pricing
6. SEC developer resources: https://www.sec.gov/about/developer-resources
7. SEC data APIs: https://data.sec.gov/
8. OpenCorporates self-serve API terms: https://opencorporates.com/legal-information/self-service-api-terms-of-service/
9. Google Maps Platform pricing: https://developers.google.com/maps/billing-and-pricing/pricing
10. Robots Exclusion Protocol, RFC 9309: https://www.rfc-editor.org/rfc/rfc9309.html
11. FTC CAN-SPAM business compliance guide: https://search.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
12. LinkedIn guidance on automated activity: https://www.linkedin.com/help/linkedin/answer/a1341543

---

## Final decision

Build the **evidence-first, explainable, safe-stop Lead Engine**. Make the first two connectors real, add the remaining connectors one by one, and test each before moving forward. Make source coverage, uncertainty, and failures visible. Use AI for evidence-grounded research and drafting, not as a substitute for data verification. Finish the workflow through approval, dry run, and caller briefing before adding live outreach.

A smaller working system that proves its claims is stronger than a large-looking system with fake records, hidden failures, or unsafe automation.
