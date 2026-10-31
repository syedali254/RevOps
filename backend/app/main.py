"""FastAPI application — the HTTP boundary between React and the backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .config import get_settings
from .connectors import ConnectorStatus, get_brave_connector
from .db import get_db, init_db
from .graph import run_workflow
from .models import Campaign, Company, SourceRecord, StageEvent, WorkflowRun, utcnow
from .safety import describe_safety, evaluate_outreach

# Rebuild pydantic models to resolve forward references
schemas.SourceRecordOut.model_rebuild()
schemas.RunOut.model_rebuild()
schemas.DiscoveryRunOut.model_rebuild()

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Local B2B Lead Engine prototype. Dry-run only: this API can never send "
        "a message to a real person."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_sources_health() -> list[schemas.SourceHealth]:
    """Dynamically report live status of all source connectors."""
    tavily_key = get_settings().tavily_api_key or ""
    exa_key = get_settings().exa_api_key or ""
    gnews_key = get_settings().gnews_api_key or ""
    brave_key = get_settings().brave_api_key or ""
    opencorp_key = get_settings().open_corporates_api_key or ""
    web_search_configured = bool(tavily_key or exa_key or brave_key)
    # Check if running in headless/mock test mode
    is_test_env = not (tavily_key or exa_key or gnews_key or brave_key or opencorp_key)

    return [
        schemas.SourceHealth(
            key="web_search",
            label="Web search (Tavily / Exa / Brave)",
            role="discovery",
            provider="Tavily AI Search" if tavily_key else ("Exa.ai" if exa_key else "Brave Search"),
            status="configured" if web_search_configured else "not_configured",
            detail="Active live web search discovery connector."
            if web_search_configured
            else "Requires TAVILY_API_KEY or EXA_API_KEY in .env.",
        ),
        schemas.SourceHealth(
            key="company_website",
            label="Company websites",
            role="enrichment",
            provider="Direct HTTP / BeautifulSoup",
            status="not_configured" if is_test_env else "configured",
            detail="Live website crawler with meta signal extraction."
            if not is_test_env
            else "Fixture fallback.",
        ),
        schemas.SourceHealth(
            key="job_postings",
            label="Public job postings",
            role="enrichment",
            provider="Greenhouse / RemoteOK API",
            status="not_configured" if is_test_env else "configured",
            detail="Live public job boards for hiring signals."
            if not is_test_env
            else "Auth-free but disabled in fixture mode.",
        ),
        schemas.SourceHealth(
            key="news_funding",
            label="News and funding",
            role="enrichment",
            provider="GNews API",
            status="configured" if gnews_key else "not_configured",
            detail="Press coverage and funding announcements."
            if gnews_key
            else "Requires GNEWS_API_KEY in .env.",
        ),
        schemas.SourceHealth(
            key="open_datasets",
            label="Business listings / SEC EDGAR",
            role="both",
            provider="SEC EDGAR & OpenCorporates",
            status="not_configured" if is_test_env else "configured",
            detail="Public corporate registry and entity filings."
            if not is_test_env
            else "Fixture fallback.",
        ),
    ]

SOURCE_HEALTH = get_sources_health()


# --- helpers ---------------------------------------------------------------


def _run_to_out(run: WorkflowRun, include_events: bool = True) -> schemas.RunOut:
    return schemas.RunOut(
        id=run.id,
        campaign_id=run.campaign_id,
        campaign_name=run.campaign.name if run.campaign else None,
        company_id=run.company_id,
        company_name=run.company.canonical_name if run.company else None,
        run_type=run.run_type,
        status=run.status,
        outcome=run.outcome,
        review_reason=run.review_reason,
        error_code=run.error_code,
        error_message=run.error_message,
        is_test_run=run.is_test_run,
        started_at=run.started_at,
        finished_at=run.finished_at,
        events=[
            schemas.StageEventOut(
                id=e.id,
                stage=e.stage,
                status=e.status,
                attempt=e.attempt,
                started_at=e.started_at,
                finished_at=e.finished_at,
                error_code=e.error_code,
                error_message=e.error_message,
                details=e.details,
            )
            for e in (run.events if include_events else [])
        ],
    )


def _campaign_out(db: Session, campaign: Campaign) -> schemas.CampaignOut:
    company_count = db.scalar(
        select(func.count()).select_from(Company).where(Company.campaign_id == campaign.id)
    )
    run_count = db.scalar(
        select(func.count()).select_from(WorkflowRun).where(WorkflowRun.campaign_id == campaign.id)
    )
    return schemas.CampaignOut(
        id=campaign.id,
        name=campaign.name,
        status=campaign.status,
        settings=campaign.settings,
        settings_version=campaign.settings_version,
        company_count=company_count or 0,
        run_count=run_count or 0,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


# --- routes ----------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    source_health_list = get_sources_health()
    groq_key = get_settings().groq_api_key or ""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "time": datetime.now(timezone.utc).isoformat(),
        "database": settings.database_url,
        "safety": describe_safety(),
        "connectors": {s.key: s.status for s in source_health_list},
        "ai": {
            "provider": "Groq" if groq_key else None,
            "status": "configured" if groq_key else "not_configured",
        },
    }


@app.get("/api/safety")
def safety() -> schemas.SafetyOut:
    return schemas.SafetyOut(**describe_safety())


@app.get("/api/safety/evaluate")
def safety_evaluate(channel: str, approved: bool = False) -> dict:
    """Dry-run verdict for a channel. Sends nothing."""
    try:
        decision = evaluate_outreach(channel, approved=approved)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return decision.__dict__


@app.get("/api/sources")
def sources() -> list[schemas.SourceHealth]:
    return get_sources_health()


# --- campaigns -------------------------------------------------------------


@app.get("/api/campaigns", response_model=list[schemas.CampaignOut])
def list_campaigns(db: Session = Depends(get_db)) -> list[schemas.CampaignOut]:
    rows = db.scalars(select(Campaign).order_by(Campaign.id.desc())).all()
    return [_campaign_out(db, c) for c in rows]


@app.post("/api/campaigns", response_model=schemas.CampaignOut, status_code=201)
def create_campaign(
    payload: schemas.CampaignCreate, db: Session = Depends(get_db)
) -> schemas.CampaignOut:
    import json

    campaign = Campaign(
        name=payload.name,
        status="draft",
        settings_json=json.dumps(payload.settings.model_dump(), ensure_ascii=False),
        settings_version=1,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign_out(db, campaign)


@app.get("/api/campaigns/{campaign_id}", response_model=schemas.CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)) -> schemas.CampaignOut:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _campaign_out(db, campaign)


# --- companies -------------------------------------------------------------


@app.get("/api/companies", response_model=list[schemas.CompanyOut])
def list_companies(
    campaign_id: int | None = None, db: Session = Depends(get_db)
) -> list[schemas.CompanyOut]:
    stmt = select(Company).order_by(Company.id.desc())
    if campaign_id is not None:
        stmt = stmt.where(Company.campaign_id == campaign_id)
    return list(db.scalars(stmt).all())


# --- workflow runs ---------------------------------------------------------


@app.post("/api/runs", response_model=schemas.RunOut, status_code=201)
def create_run(payload: schemas.RunCreate, db: Session = Depends(get_db)) -> schemas.RunOut:
    campaign = db.get(Campaign, payload.campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    company: Company | None
    if payload.company_id is not None:
        company = db.get(Company, payload.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        if company.campaign_id != campaign.id:
            raise HTTPException(
                status_code=422, detail="Company does not belong to this campaign"
            )
    else:
        assert payload.company is not None
        normalized = payload.company.canonical_name.strip().lower()
        company = Company(
            campaign_id=campaign.id,
            canonical_name=payload.company.canonical_name,
            normalized_name=normalized,
            website_domain=payload.company.website_domain,
            country=payload.company.country,
            sector=payload.company.sector,
            employee_min=payload.company.employee_min,
            employee_max=payload.company.employee_max,
            # In Milestone 1 every company is entered by hand: label it honestly.
            record_kind="test_seed",
            workflow_status="discovered",
        )
        db.add(company)
        db.flush()
        db.add(
            SourceRecord(
                company_id=company.id,
                source_type="manual_test_seed",
                provider="user_input",
                status="success_with_results",
                source_url=None,
                raw_payload_json=None,
            )
        )
        db.commit()
        db.refresh(company)

    run = WorkflowRun(
        campaign_id=campaign.id,
        company_id=company.id,
        run_type="qualification",
        status="running",
        is_test_run=True,
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # LangGraph owns the transition; the API only records the entry point.
    try:
        run_workflow(run.id, fail_at=payload.fail_at)
    except Exception as exc:  # pragma: no cover - graph traps its own errors
        run.status = "failed"
        run.outcome = "stopped_after_error"
        run.error_code = "graph_failure"
        run.error_message = f"{type(exc).__name__}: {exc}"
        run.finished_at = utcnow()
        db.commit()

    db.refresh(run)
    return _run_to_out(run)


@app.get("/api/runs", response_model=list[schemas.RunOut])
def list_runs(
    campaign_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[schemas.RunOut]:
    stmt = select(WorkflowRun).order_by(WorkflowRun.id.desc()).limit(min(limit, 200))
    if campaign_id is not None:
        stmt = stmt.where(WorkflowRun.campaign_id == campaign_id)
    return [_run_to_out(r) for r in db.scalars(stmt).all()]


@app.get("/api/runs/{run_id}", response_model=schemas.RunOut)
def get_run(run_id: int, db: Session = Depends(get_db)) -> schemas.RunOut:
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return _run_to_out(run)


@app.post("/api/runs/{run_id}/retry", response_model=schemas.RunOut, status_code=201)
def retry_run(run_id: int, db: Session = Depends(get_db)) -> schemas.RunOut:
    """Re-run the same campaign/company without creating a duplicate company."""
    original = db.get(WorkflowRun, run_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    run = WorkflowRun(
        campaign_id=original.campaign_id,
        company_id=original.company_id,
        status="running",
        is_test_run=original.is_test_run,
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    run_workflow(run.id, fail_at=None)
    db.refresh(run)
    return _run_to_out(run)


@app.post("/api/runs/{run_id}/events", response_model=schemas.StageEventOut, status_code=201)
def log_manual_event(
    run_id: int,
    payload: dict,
    db: Session = Depends(get_db),
) -> schemas.StageEventOut:
    """Append a manually logged event (human decision), clearly marked as manual."""
    run = db.get(WorkflowRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")

    import json

    event = StageEvent(
        run_id=run.id,
        stage=str(payload.get("stage", "manual_note")),
        status=str(payload.get("status", "ok")),
        started_at=utcnow(),
        finished_at=utcnow(),
        error_message=payload.get("message"),
        details_json=json.dumps(
            {"manual": True, **(payload.get("details") or {})}, ensure_ascii=False, default=str
        ),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return schemas.StageEventOut(
        id=event.id,
        stage=event.stage,
        status=event.status,
        attempt=event.attempt,
        started_at=event.started_at,
        finished_at=event.finished_at,
        error_code=event.error_code,
        error_message=event.error_message,
        details=event.details,
    )


# --- discovery runs --------------------------------------------------------


def _discovery_run_to_out(run: WorkflowRun) -> schemas.DiscoveryRunOut:
    event_list = list(run.events)
    companies_discovered = sum(
        1
        for e in event_list
        if e.stage == "find"
        for detail in [e.details]
        if detail.get("created_companies")
        for _ in detail.get("created_companies", [])
    )
    companies_created = companies_discovered
    duplicates_found = sum(
        1
        for e in event_list
        if e.stage == "find"
        for detail in [e.details]
        if detail.get("duplicates")
        for _ in detail.get("duplicates", [])
    )

    return schemas.DiscoveryRunOut(
        id=run.id,
        campaign_id=run.campaign_id,
        campaign_name=run.campaign.name if run.campaign else None,
        run_type=run.run_type,
        status=run.status,
        outcome=run.outcome,
        review_reason=run.review_reason,
        error_code=run.error_code,
        error_message=run.error_message,
        is_test_run=run.is_test_run,
        started_at=run.started_at,
        finished_at=run.finished_at,
        events=[
            schemas.StageEventOut(
                id=e.id,
                stage=e.stage,
                status=e.status,
                attempt=e.attempt,
                started_at=e.started_at,
                finished_at=e.finished_at,
                error_code=e.error_code,
                error_message=e.error_message,
                details=e.details,
            )
            for e in event_list
        ],
        companies_discovered=companies_discovered,
        companies_created=companies_created,
        duplicates_found=duplicates_found,
    )


@app.post("/api/discovery", response_model=schemas.DiscoveryRunOut, status_code=201)
def create_discovery_run(
    payload: schemas.DiscoveryRunCreate, db: Session = Depends(get_db)
) -> schemas.DiscoveryRunOut:
    campaign = db.get(Campaign, payload.campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Apply max_results override to campaign settings for this run
    settings = campaign.settings.copy()
    if payload.max_results is not None:
        settings["max_discovery_results"] = payload.max_results

    run = WorkflowRun(
        campaign_id=campaign.id,
        company_id=None,  # Discovery runs don't have a single company upfront
        run_type="discovery",
        status="running",
        is_test_run=True,
        started_at=utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Run discovery workflow (only the find node for now)
    try:
        # We need to temporarily store the settings override for the graph
        # The graph reads settings from the campaign, so we update it temporarily
        original_settings_json = campaign.settings_json
        import json

        campaign.settings_json = json.dumps(settings, ensure_ascii=False)
        db.add(campaign)
        db.commit()

        run_workflow(run.id, fail_at=payload.fail_at)

        # Restore original settings
        campaign.settings_json = original_settings_json
        db.add(campaign)
        db.commit()
    except Exception as exc:
        run.status = "failed"
        run.outcome = "stopped_after_error"
        run.error_code = "graph_failure"
        run.error_message = f"{type(exc).__name__}: {exc}"
        run.finished_at = utcnow()
        db.commit()

    db.refresh(run)
    return _discovery_run_to_out(run)


@app.get("/api/discovery", response_model=list[schemas.DiscoveryRunOut])
def list_discovery_runs(
    campaign_id: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[schemas.DiscoveryRunOut]:
    stmt = (
        select(WorkflowRun)
        .where(WorkflowRun.run_type == "discovery")
        .order_by(WorkflowRun.id.desc())
        .limit(min(limit, 200))
    )
    if campaign_id is not None:
        stmt = stmt.where(WorkflowRun.campaign_id == campaign_id)
    return [_discovery_run_to_out(r) for r in db.scalars(stmt).all()]


@app.get("/api/discovery/{run_id}", response_model=schemas.DiscoveryRunOut)
def get_discovery_run(run_id: int, db: Session = Depends(get_db)) -> schemas.DiscoveryRunOut:
    run = db.get(WorkflowRun, run_id)
    if run is None or run.run_type != "discovery":
        raise HTTPException(status_code=404, detail="Discovery run not found")
    return _discovery_run_to_out(run)


# --- source records --------------------------------------------------------


class SourceRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int | None
    source_type: str
    provider: str
    source_url: str | None
    retrieved_at: datetime
    published_at: datetime | None
    status: str
    error_message: str | None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/companies/{company_id}/sources")
def list_company_sources(company_id: int, db: Session = Depends(get_db)) -> list[schemas.SourceRecordOut]:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    records = db.scalars(
        select(SourceRecord)
        .where(SourceRecord.company_id == company_id)
        .order_by(SourceRecord.retrieved_at.desc())
    ).all()

    import json

    return [
        schemas.SourceRecordOut(
            id=r.id,
            company_id=r.company_id,
            source_type=r.source_type,
            provider=r.provider,
            source_url=r.source_url,
            retrieved_at=r.retrieved_at,
            published_at=r.published_at,
            status=r.status,
            error_message=r.error_message,
            raw_payload=json.loads(r.raw_payload_json or "{}") if r.raw_payload_json else {},
        )
        for r in records
    ]


# --- company list & detail ---------------------------------------------------


@app.get("/api/campaigns/{campaign_id}/companies", response_model=list[schemas.CompanyListItem])
def list_campaign_companies(campaign_id: int, db: Session = Depends(get_db)) -> list[schemas.CompanyListItem]:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    companies = db.scalars(
        select(Company)
        .where(Company.campaign_id == campaign_id)
        .order_by(Company.id.desc())
    ).all()

    return [schemas.CompanyListItem.model_validate(c) for c in companies]


@app.get("/api/companies/needing-review", response_model=list[schemas.CompanyListItem])
def list_companies_needing_review(db: Session = Depends(get_db)) -> list[schemas.CompanyListItem]:
    """Get all companies that need human review (qualification_status = 'needs_review')."""
    companies = db.scalars(
        select(Company)
        .where(Company.qualification_status == "needs_review")
        .order_by(Company.id.desc())
    ).all()

    return [schemas.CompanyListItem.model_validate(c) for c in companies]


@app.get("/api/companies/{company_id}", response_model=schemas.CompanyDetail)
def get_company(company_id: int, db: Session = Depends(get_db)) -> schemas.CompanyDetail:
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    sources = db.scalars(
        select(SourceRecord)
        .where(SourceRecord.company_id == company_id)
        .order_by(SourceRecord.retrieved_at.desc())
    ).all()

    import json

    company_data = schemas.CompanyDetail.model_validate(company)
    company_data.sources = [
        schemas.SourceRecordOut(
            id=r.id,
            company_id=r.company_id,
            source_type=r.source_type,
            provider=r.provider,
            source_url=r.source_url,
            retrieved_at=r.retrieved_at,
            published_at=r.published_at,
            status=r.status,
            error_message=r.error_message,
            raw_payload=json.loads(r.raw_payload_json or "{}") if r.raw_payload_json else {},
        )
        for r in sources
    ]

    return company_data


@app.post("/api/companies/{company_id}/approve", response_model=schemas.CompanyDetail)
def approve_company(company_id: int, db: Session = Depends(get_db)) -> schemas.CompanyDetail:
    """Approve a company for outreach."""
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company.approval_status = "approved"
    company.approved_at = utcnow()
    db.commit()
    db.refresh(company)

    return get_company(company_id=company_id, db=db)


@app.post("/api/companies/{company_id}/reject", response_model=schemas.CompanyDetail)
def reject_company(company_id: int, db: Session = Depends(get_db)) -> schemas.CompanyDetail:
    """Reject a company (mark as not suitable for outreach)."""
    company = db.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company.approval_status = "rejected"
    company.approved_at = utcnow()
    db.commit()
    db.refresh(company)

    return get_company(company_id=company_id, db=db)


# --- overview --------------------------------------------------------------


@app.get("/api/overview", response_model=schemas.OverviewOut)
def overview(db: Session = Depends(get_db)) -> schemas.OverviewOut:
    campaign_count = db.scalar(select(func.count()).select_from(Campaign)) or 0
    company_total = db.scalar(select(func.count()).select_from(Company)) or 0
    test_count = (
        db.scalar(
            select(func.count())
            .select_from(Company)
            .where(Company.record_kind == "test_seed")
        )
        or 0
    )
    run_total = db.scalar(select(func.count()).select_from(WorkflowRun)) or 0

    status_rows = db.execute(
        select(WorkflowRun.status, func.count()).group_by(WorkflowRun.status)
    ).all()
    runs_by_status = {str(status): int(count) for status, count in status_rows}

    recent_runs = db.scalars(
        select(WorkflowRun).order_by(WorkflowRun.id.desc()).limit(5)
    ).all()

    # Count discovery runs separately
    discovery_run_total = db.scalar(
        select(func.count()).select_from(WorkflowRun).where(WorkflowRun.run_type == "discovery")
    ) or 0

    next_actions: list[str] = []
    if campaign_count == 0:
        next_actions.append("Create a campaign to define the target profile.")
    else:
        next_actions.append("Run the workflow for a company to see stage history.")
    if run_total == 0 and discovery_run_total == 0:
        next_actions.append("No workflow runs yet — start one from the Campaigns page.")
    elif runs_by_status.get("needs_review", 0):
        next_actions.append(
            f"{runs_by_status['needs_review']} run(s) need human review before they can advance."
        )
    elif runs_by_status.get("failed", 0):
        next_actions.append(
            f"{runs_by_status['failed']} run(s) stopped after an error — inspect the run details."
        )

    source_health_list = get_sources_health()

    return schemas.OverviewOut(
        generated_at=utcnow(),
        counts=schemas.OverviewCounts(
            campaigns=campaign_count,
            companies=company_total,
            test_companies=test_count,
            retrieved_companies=max(company_total - test_count, 0),
            runs=run_total,
            runs_by_status=runs_by_status,
        ),
        safety=schemas.SafetyOut(**describe_safety()),
        sources=source_health_list,
        recent_runs=[_run_to_out(r) for r in recent_runs],
        next_actions=next_actions,
    )
