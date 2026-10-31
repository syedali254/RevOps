# B2B Lead Engine — Comprehensive System & Product Blueprint

**Author:** Technical Engineering & Development Team  
**Date:** October 2026  
**Document Version:** 1.0 (Production Blueprint & Architecture Review)  
**Target Audience:** Engineering Leadership, Product Management, Commercial Stakeholders  

---

## 1. Executive Summary & Product Vision

Modern B2B outbound engines face a critical credibility crisis. Traditional sales automation tools ("sales engagement platforms") prioritize raw email volume and scraped lead lists over data veracity. The results are well-documented across the industry: high bounce rates, ruined domain reputations, spam filtering, legal compliance fines (CAN-SPAM, GDPR, TCPA), and cold outreach that prospects immediately identify as generic AI slop.

The **B2B Lead Engine** is designed with the opposite philosophy: **Precision, Corroboration, Transparency, and Safety.**

Rather than blasting thousands of unverified contacts, this system operates as an **autonomous sales intelligence dossier engine**. It discovers legitimate B2B technology companies, corroborates facts across multiple independent public sources, scores leads with zero guesswork, generates personalized research briefings via Groq AI, and hands human sales callers an exhaustive **9-Panel Briefing Dossier** before any call is placed.

Most critically, **live message dispatch is blocked by code** in a strict Dry-Run safety sandbox until management formally clears outreach compliance.

---

## 2. Core Architectural & Strategic Decisions ("Why This, Why Not That")

### 2.1 Why Live Multi-Source Discovery Instead of Hardcoded Lead Lists or Fixtures?
- **The Problem with Fixtures / Hardcoded Lists**: Static CSVs and fixture mockups go stale within weeks. Companies pivot, change headcounts, hire new leadership, or shut down. Testing against mock data hides the real friction of the internet: network timeouts, malformed HTML, empty search queries, and dynamic site layouts.
- **Our Live Approach**: We connected live discovery APIs (**Tavily AI Search**, **Exa.ai Neural Search**, and configured **Brave Search**). When a campaign targets *"B2B SaaS companies in Los Angeles"*, the engine queries live web indices and surfaces real companies active in the market today.
- **Corroboration Requirement**: No single search engine has complete web coverage. Operating with multiple discovery connectors allows automatic fallback: if Tavily is saturated, Exa’s neural semantic index provides secondary coverage.

### 2.2 Why We Strictly Avoid LinkedIn Scraping and Browser Automation
- **Account Ban Risk**: Automated scraping behind LinkedIn logins violates Section 8.2 of LinkedIn's User Agreement. Using headless Chrome (Puppeteer/Playwright) to scrape user profiles routinely leads to IP blocks, CAPTCHA hurdles, and permanent sales account termination.
- **Legal & Compliance Integrity**: Scraping behind authenticated walls poses severe legal liabilities. Our engine focuses exclusively on **open, public web intelligence**:
  1. Public corporate websites and metadata tags.
  2. Indexable press releases and funding news (via GNews).
  3. Official regulatory submissions (via the U.S. Securities and Exchange Commission EDGAR public registry).
  4. Public job boards (Greenhouse API and RemoteOK).
  5. Official corporate registers (OpenCorporates).

### 2.3 Why LangGraph for Workflow Orchestration (and Not n8n or Custom Ad-Hoc Scripts)?
- **n8n / Low-Code Limitations**: Visual drag-and-drop tools like n8n or Zapier struggle with complex branching, deterministic state rollbacks, local SQLite/PostgreSQL persistence, and granular testability via `pytest`.
- **Ad-Hoc Python Scripts**: Simple script pipelines usually fail silently, mix API calls with business logic, and lack a durable execution state. If stage 6 fails, the entire script crashes and data from stages 1–5 is lost.
- **LangGraph Advantage**:
  - Treats each sales research stage (`start`, `find`, `merge`, `evaluate`, `website_enrichment`, `jobs_enrichment`, `news_enrichment`, `sec_enrichment`, `scoring`, `research`, `approval`, `dry_run`, `finish`) as an explicit node in a compiled directed graph.
  - State is typed, immutable, and persisted at every step.
  - Transparent conditional routing: companies with unverified facts are routed to a **Human Review Queue** rather than allowed to advance blindly.

### 2.4 Why Groq Cloud (Llama 3.3 70B) for Research & Briefing Generation?
- **Zero Hallucination Grounding**: Standard LLMs hallucinate customer names, tech stacks, and revenues when asked open-ended questions. In our engine, Groq Cloud is fed **only the corroborated evidence records** harvested in previous stages. It is strictly constrained by prompt contracts: *if a fact is not in the evidence payload, the model must explicitly declare it "Unknown"*.
- **Sub-Second Inference Speed**: Groq’s LPU (Language Processing Unit) architecture delivers generation speeds 5–10x faster than traditional GPU clusters, enabling rapid real-time dossier generation during qualification workflows.

### 2.5 Why the Backend-Enforced Dry-Run Guard?
- Compliance with global outreach regulations (CAN-SPAM Act, TCPA Do-Not-Call registries, and GDPR legitimate interest rules) demands absolute safety.
- The `DRY_RUN=true` flag is **not a UI cosmetic switch**. It is enforced at the core Python domain layer in `backend/app/safety.py`. Every attempt to transmit an email, SMS, or LinkedIn message raises a `SendNotPermittedError` and logs a simulated event audit trail.

---

## 3. End-to-End System Workflow

```
[ Campaign Configuration ] (Sectors, Countries, Headcount Brackets, Target Titles)
            │
            ▼
[ Stage 1: Live Discovery ] ──► (Tavily Search API / Exa.ai / YC Directory)
            │
            ▼
[ Stage 2: Entity Normalization & Deduplication ] ──► (Merge identical domains, prevent duplicates)
            │
            ▼
[ Stage 3: Multi-Source Enrichment ]
      ├── 3a. Direct Website Crawler (Homepage meta, title, semantic tags)
      ├── 3b. Public Job Boards (Greenhouse API, RemoteOK for hiring signals)
      ├── 3c. Press & Media Monitoring (GNews API for funding/product news)
      ├── 3d. Regulatory Registries (SEC EDGAR public filings, OpenCorporates)
            │
            ▼
[ Stage 4: Deterministic Scoring (0–100) ]
      ├── Factor 1: Company Fit (0–40 pts: Country, Sector, Employee Bracket)
      ├── Factor 2: Evidence Quality (0–25 pts: Multi-provider corroboration, recency)
      ├── Factor 3: Business Relevance (0–20 pts: Technology signals, market focus)
      └── Factor 4: Contactability (0–15 pts: Verified website, corporate email domain)
            │
            ▼
[ Stage 5: AI Research Briefing & Personalization ] ──► (Groq Cloud LLM synthesis)
            │
            ▼
[ Stage 6: Human Approval Gate ] ──► (Manager reviews 9-panel dossier: Approve or Reject)
            │
            ▼
[ Stage 7: Dry-Run Guard & Caller Briefing ] ──► (Simulated dispatch log + Caller Dossier ready)
```

---

## 4. Detailed Breakdown: The 9-Panel Caller Briefing Dossier

The central deliverable of the engine is the **Caller Briefing Dossier**. Before a sales representative or SDR dials a prospect, they are presented with a unified single-screen dossier divided into 9 standardized panels:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CALLER BRIEFING DOSSIER                         │
├────────────────────────┬───────────────────────┬───────────────────────┤
│ 1. Core Profile        │ 2. Size & Structure   │ 3. Hiring Signals     │
│  - Legal Name          │  - Employee Bracket   │  - Open Vacancies     │
│  - Website & Domain    │  - Growth Scale       │  - Tech Stack Clues   │
│  - Country / Location  │  - Source Confidence  │  - Source: Greenhouse │
├────────────────────────┼───────────────────────┼───────────────────────┤
│ 4. News & Regulatory   │ 5. Web Extraction     │ 6. Discovery Origin   │
│  - GNews Headlines     │  - Scraped Meta Tags  │  - Discovered Provider│
│  - SEC EDGAR Filings   │  - HTTP Status / SSR  │  - Direct Proof URL   │
│  - Verified Timestamps │  - Homepage Synopsis  │  - Raw Audit Payload  │
├────────────────────────┼───────────────────────┼───────────────────────┤
│ 7. AI Research Brief   │ 8. Caller Opening Line│ 9. Compliance Guard   │
│  - Grounded Synthesis  │  - Contextual Hook    │  - Dry-Run Status     │
│  - Verified Facts Only │  - Tailored Angle     │  - Blocked Channels   │
│  - Clear Unknown Gaps  │  - Value Proposition  │  - Audit Trail Stamp  │
└────────────────────────┴───────────────────────┴───────────────────────┘
```

### Detailed Panel Specifications:

#### Panel 1: Core Company Profile (Identity)
- **What it displays**: Canonical legal name, primary verified website domain, corporate headquarters location, and classified industry sector.
- **Why it matters**: Eliminates confusion between subsidiary brands, parent holding companies, or ambiguous product names.

#### Panel 2: Verified Size & Structure (Scale)
- **What it displays**: Employee range bracket (e.g. `20–200 employees`), confidence rating, and origin classification (`live crawler retrieval` vs `campaign seed`).
- **Why it matters**: Prevents sales reps from pitching enterprise packages to 3-person seed startups, or SMB packages to global enterprises.

#### Panel 3: Hiring & Growth Signals (Expansion Indicators)
- **What it displays**: Active open job positions extracted from public applicant tracking systems (Greenhouse Job Boards and RemoteOK).
- **Why it matters**: A company hiring senior engineers or account executives has active budget and urgent operational friction—the single highest-converting trigger in B2B outbound.

#### Panel 4: Press, News & Regulatory Filings (Market Velocity)
- **What it displays**: Verified news articles from the GNews API and official regulatory filings from the U.S. SEC EDGAR system (Forms D, 10-K, 8-K).
- **Why it matters**: Enables the caller to reference genuine recent company milestones (e.g., Series A funding or acquisitions) within the first 10 seconds of a phone conversation.

#### Panel 5: Web Crawler Signals (Digital Footprint)
- **What it displays**: Structured data scraped live from the target’s homepage: title tags, meta descriptions, semantic headers, and open-graph tags.
- **Why it matters**: Shows exactly how the company describes its own value proposition in its own words today.

#### Panel 6: Discovery Origin & Proof (Audit Verification)
- **What it displays**: The original search provider (Tavily, Exa, Brave) that identified the lead, the exact source URL, and the retrieval ISO timestamp.
- **Why it matters**: Complete transparency. If an SDR asks *"Where did we find this company?"*, the exact URL and proof record are visible in one click.

#### Panel 7: Comprehensive AI Research Brief (Context Synthesis)
- **What it displays**: A structured markdown briefing generated by Groq Cloud (Llama 3.3 70B) synthesizing company overview, verified facts, evidence sources, and—crucially—**explicit unknowns & verification gaps**.
- **Why it matters**: Eliminates 20 minutes of manual pre-call Google searching per prospect. The caller digests the entire account context in 60 seconds.

#### Panel 8: Caller Opening Line (Personalized Conversation Hook)
- **What it displays**: A suggested natural conversational opening line that connects a real public fact to the agency's value proposition.
- **Why it matters**: Moves sales reps away from robotic elevator pitches ("*I wanted to introduce our company...*") toward contextual opening questions ("*I saw your expansion in cloud infrastructure across Los Angeles...*").

#### Panel 9: Compliance & Dry-Run Safety Guard (Legal Assurance)
- **What it displays**: Safety status badge (`NO SEND — DRY RUN ONLY`), confirmation of backend code guards, and simulated outreach log entries.
- **Why it matters**: Gives stakeholders and compliance officers ironclad confidence that no automated messages are leaving the server unauthorized.

---

## 5. Current Dashboard Implementation & Live Capabilities

The user interface is built on **React, TypeScript, Vite, and Tailwind CSS**, featuring an executive B2B SaaS design system with dark-slate navigation (`#0f1422`) and light surface operational panels:

1. **Top Global Bar**: Persistent, amber-accented status bar reminding all operators: `DRY RUN — NO MESSAGES SENT`.
2. **Overview Dashboard (`/`)**:
   - Live metrics: Total Campaigns, Total Discovered Companies, Total LangGraph Workflow Runs, and Leads Needing Attention.
   - Connector Health Table: Real-time configuration status for Tavily, Exa, Brave, Website Crawler, Greenhouse, GNews, SEC EDGAR, and Groq AI.
   - Recent Workflow Activity Feed with direct drill-down links.
3. **Campaigns Management (`/campaigns`)**:
   - Campaign creator defining custom qualification boundaries (target countries, target sectors, employee brackets, required domains).
   - "Start Discovery" modal: Triggers live Tavily/Exa web searches with customizable result limits.
4. **Company Directory (`/campaigns/:id/companies`)**:
   - Clean tabular overview of all discovered and qualified leads.
   - Displays real-time Score, Evidence Confidence, Qualification Status pill, and **Dossier Action Link**.
5. **Company Detail & Dossier Page (`/campaigns/:cid/companies/:id`)**:
   - Instant **"Run qualification"** button to execute the full LangGraph enrichment, scoring, and research pipeline on demand.
   - Full 9-Panel Dossier rendering.
   - Interactive **Approve Lead** and **Reject Lead** actions.
   - Complete Corroborated Evidence Audit Trail table with active links to source URLs.
6. **Human Review Queue (`/review`)**:
   - Dedicated filtering queue displaying all leads held for human judgment (scores 0–49 or conflicting data points).
7. **Workflow Runs Inspector (`/runs` and `/runs/:id`)**:
   - Granular event timeline tracking every LangGraph stage attempt, duration, payload details, and error recovery logs.

---

## 6. Current Implementation Status & Provider Breakdown

| Provider / Tool | Category | Status in Prototype | Notes & Production Roadmap |
|:---|:---|:---|:---|
| **Tavily AI Search** | Discovery | **Active & Live** | Working as primary search discovery engine via API key. |
| **Exa.ai** | Discovery | **Active & Live** | Configured as secondary neural semantic search engine. |
| **Brave Search API** | Discovery | **Configured** | Code complete. Requires active card verification on Brave dashboard. |
| **Y Combinator Directory**| Discovery | **Directory Mode** | Currently matching YC profiles; building automated direct CSV sync. |
| **Direct Web Crawler** | Enrichment | **Active & Live** | Native Python HTTP + BeautifulSoup scraper collecting live HTML tags. |
| **Greenhouse API** | Enrichment | **Active & Live** | Queries public job boards for active hiring growth indicators. |
| **RemoteOK API** | Enrichment | **Active & Live** | Public tech job listings for technology stack corroboration. |
| **GNews API** | Enrichment | **Active & Live** | Live news API querying press releases and funding coverage. |
| **SEC EDGAR** | Enrichment | **Active & Live** | Queries official U.S. SEC public submission endpoints (auth-free). |
| **OpenCorporates** | Enrichment | **Configured** | Commercial registry integration ready for enterprise API key. |
| **Groq Cloud (Llama 3.3)** | Intelligence | **Active & Live** | Sub-second AI synthesis for research briefs and opening lines. |
| **Dry-Run Engine** | Compliance | **Active & Live** | Backend-enforced guard blocking all 5 communication channels. |

---

## 7. Strategic Roadmap to Full Enterprise Production

To transition this high-fidelity prototype into an autonomous, enterprise-grade production platform, the engineering roadmap focuses on three horizons:

### Horizon 1: Data Ingestion & Dataset Automation (Short-Term: Weeks 1–2)
- **Automated YC Directory Scraper/Sync**: Build a scheduled daily background job that pulls Y Combinator’s public directory (`ycombinator.com/companies`) directly into the SQLite/PostgreSQL database, categorizing startups by batch (e.g., W24, S24) and geography automatically.
- **Brave Search Card Activation**: Activate the commercial tier of Brave Search to unlock independent web index discovery without search quota constraints.

### Horizon 2: Corroboration Expansion & Tech-Stack Fingerprinting (Mid-Term: Weeks 3–4)
- **BuiltWith / Wappalyzer Integration**: Add technology stack fingerprinting to detect CRM tools, marketing automation platforms, and cloud infrastructure directly from DNS and JavaScript bundle inspection.
- **Multi-Factor Executive Identification**: Corroborate C-level executive names across corporate "About Us" pages, SEC signatures, and public press releases to establish verified decision-maker records.

### Horizon 3: Multi-Channel Outreach Release & CRM Hand-Off (Production Ready: Weeks 5–6)
- **CRM Integration (GoHighLevel / HubSpot)**: Implement bidirectional syncing. Once a lead is Approved in the Review Queue, its 9-Panel Dossier and verified contact record push directly into GoHighLevel custom fields.
- **Granular Outreach Gate Releases**: Enable live sending channel-by-channel with founder approval:
  1. *Phase A*: Email channel with automated SPF/DKIM validation and Google Workspace warmup throttling.
  2. *Phase B*: Sales phone dialer integration with automatic National Do-Not-Call (DNC) list checking.
  3. *Phase C*: Web form submission engine with CAPTCHA-respecting human intervention checkpoints.

---

## 8. Conclusion & Leadership Summary

The **B2B Lead Engine** has transitioned from a conceptual architectural plan to a **fully functioning, demonstrable prototype**. 

It proves that high-performing outbound does not require spamming thousands of unverified contacts or violating platform terms of service. By combining **live search APIs, deterministic multi-source corroboration, LangGraph state orchestration, Groq AI inference, and strict dry-run compliance**, the system provides sales callers with an unfair competitive advantage: **unimpeachable facts, immediate context, and zero wasted conversations.**

The foundation is built, all automated tests pass, and the platform is ready for expanded provider volume.
