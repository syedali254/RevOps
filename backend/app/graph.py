"""The Milestone 1 LangGraph workflow.

LangGraph owns state, nodes and conditional routing. The node bodies are plain
Python functions that read/write the database; they never decide what happens
next on their own.

Graph:

    START -> start -> find -> merge -> [evaluate | hold_for_review]
                                        |
                                        v
                       [finish | hold_for_review | reject | stop_after_error] -> END

Honest outcomes:
    continue             the stage finished, the next stage may run
    needs_human_review   an unknown / conflicting / duplicate condition held the record
    rejected             a required campaign condition clearly failed
    stopped_after_error  a task raised; the run stops and the record does not advance
"""

from __future__ import annotations

import functools
import json
import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from .connectors import (
    ConnectorStatus,
    DiscoveryQuery,
    EnrichmentQuery,
    get_brave_connector,
    get_exa_connector,
    get_greenhouse_connector,
    get_gnews_connector,
    get_hn_connector,
    get_opencorporates_connector,
    get_remoteok_connector,
    get_sec_connector,
    get_tavily_connector,
    get_website_connector,
    get_yc_connector,
)
from .db import session_scope
from .models import Company, Campaign, SourceRecord, StageEvent, WorkflowRun, utcnow
from .research import generate_research_brief
from .scoring import ScoreResult, score_company


class StageError(RuntimeError):
    """A task failed in a way that must stop the run."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class GraphState(TypedDict, total=False):
    run_id: int
    campaign_id: int
    company_id: int
    company_name: str
    record_kind: str
    website_domain: str | None
    country: str | None
    sector: str | None
    employee_min: int | None
    employee_max: int | None
    settings: dict[str, Any]
    fail_at: str | None

    # For discovery runs: multiple companies created
    created_company_ids: list[int]
    # For discovery runs: run_type
    run_type: str

    stage: str
    outcome: str | None
    decision: str | None
    findings: Annotated[list[str], operator.add]
    checks: list[dict[str, Any]]
    review_reason: str | None
    error_code: str | None
    error: str | None


def _dump(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str, ensure_ascii=False)


def emit_event(
    run_id: int,
    stage: str,
    status: str,
    started_at: datetime,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
    details: Any = None,
) -> None:
    """Append one structured stage event. Never raises into the graph."""
    try:
        with session_scope() as db:
            db.add(
                StageEvent(
                    run_id=run_id,
                    stage=stage,
                    status=status,
                    started_at=started_at,
                    finished_at=utcnow(),
                    error_code=error_code,
                    error_message=error_message,
                    details_json=_dump(details),
                )
            )
    except Exception:  # pragma: no cover - logging must not break the workflow
        pass


def _maybe_force_failure(state: GraphState, stage: str) -> None:
    """Test control: `fail_at` deliberately exercises the error path.

    It is opt-in per run and is reported as a simulated failure so nobody can
    mistake it for a real provider error.
    """
    if state.get("fail_at") == stage:
        raise StageError(
            "forced_test_failure",
            f"Simulated failure requested by the test control 'fail_at={stage}'. "
            "This is a deliberate test signal, not a real provider error.",
        )


def _stage(stage_name: str):
    """Wrap a node so it always writes a timestamped event and never escapes an exception."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(state: GraphState) -> dict[str, Any]:
            started = utcnow()
            try:
                _maybe_force_failure(state, stage_name)
                updates = fn(state) or {}
            except StageError as exc:
                emit_event(
                    state.get("run_id", 0),
                    stage_name,
                    "failed",
                    started,
                    error_code=exc.code,
                    error_message=str(exc),
                    details={"forced": state.get("fail_at") == stage_name},
                )
                updates = {
                    "stage": stage_name,
                    "outcome": "stopped_after_error",
                    "error_code": exc.code,
                    "error": str(exc),
                }
            except Exception as exc:  # noqa: BLE001 - converted into an honest failure
                emit_event(
                    state.get("run_id", 0),
                    stage_name,
                    "failed",
                    started,
                    error_code="unexpected_error",
                    error_message=f"{type(exc).__name__}: {exc}",
                )
                updates = {
                    "stage": stage_name,
                    "outcome": "stopped_after_error",
                    "error_code": "unexpected_error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            else:
                emit_event(
                    state.get("run_id", 0),
                    stage_name,
                    updates.pop("_event_status", "ok"),
                    started,
                    details=updates.pop("_event_details", None),
                )
            return updates

        return wrapper

    return decorator


# --- nodes -----------------------------------------------------------------


@_stage("start")
def start_node(state: GraphState) -> dict[str, Any]:
    return {
        "stage": "start",
        "outcome": "continue",
        "findings": [
            f"Run opened for '{state.get('company_name', '')}' "
            f"(record kind: {state.get('record_kind', 'unknown')})."
        ],
        "checks": [],
        "review_reason": None,
        "error_code": None,
        "error": None,
        "_event_details": {
            "campaign_id": state.get("campaign_id"),
            "company_id": state.get("company_id"),
            "record_kind": state.get("record_kind"),
        },
    }


@_stage("find")
def find_node(state: GraphState) -> dict[str, Any]:
    """DISCOVERY stage.

    For discovery runs: runs the enabled discovery connectors against the campaign criteria,
    creates candidate companies and source records for each result.

    Priority order: Tavily (live) -> Exa (live fallback) -> Brave (fixture if no key)

    For qualification runs: records that the single company was already created manually
    or retrieved, and adds a source record if needed.
    """
    run_id = state.get("run_id")
    campaign_id = state.get("campaign_id")
    run_type = state.get("run_type", "qualification")

    if run_type == "discovery":
        # Discovery run: find multiple candidates from connectors
        settings = state.get("settings") or {}
        query = DiscoveryQuery(
            campaign_id=campaign_id,
            countries=settings.get("countries", []),
            sectors=settings.get("sectors", []),
            employee_min=settings.get("employee_min"),
            employee_max=settings.get("employee_max"),
            max_results=settings.get("max_discovery_results", 50),
        )

        # Discovery connectors in priority order
        # Live connectors: Tavily (primary), Exa (fallback), Remote OK
        # Fixture/CSV: Brave, YC (CSV import)
        import asyncio

        loop = asyncio.new_event_loop()
        all_candidates = []
        connector_results = []
        hn_notes: list[str] = []  # best-effort notes; merged into the event details

        try:
            # Try Tavily first (live primary)
            tavily_connector = get_tavily_connector()
            tavily_result = loop.run_until_complete(tavily_connector.discover(query))
            connector_results.append(("tavily", tavily_result))
            if tavily_result.is_success() and tavily_result.candidates:
                all_candidates.extend(("tavily", c) for c in tavily_result.candidates)

            # Try Exa (live fallback)
            exa_connector = get_exa_connector()
            exa_result = loop.run_until_complete(exa_connector.discover(query))
            connector_results.append(("exa", exa_result))
            if exa_result.is_success() and exa_result.candidates:
                all_candidates.extend(("exa", c) for c in exa_result.candidates)

            # Try Remote OK (live job feed discovery)
            remoteok_connector = get_remoteok_connector()
            remoteok_result = loop.run_until_complete(remoteok_connector.discover(query))
            connector_results.append(("remoteok", remoteok_result))
            if remoteok_result.is_success() and remoteok_result.candidates:
                all_candidates.extend(("remoteok", c) for c in remoteok_result.candidates)

            # Try Hacker News Who-is-Hiring (free, public API, best-effort)
            hn_connector = get_hn_connector()
            try:
                hn_result = loop.run_until_complete(hn_connector.discover(query))
                connector_results.append(("hn", hn_result))
                if hn_result.is_success() and hn_result.candidates:
                    all_candidates.extend(("hn", c) for c in hn_result.candidates)
            except Exception as hn_exc:  # noqa: BLE001 - HN is optional, never fatal
                hn_notes.append(
                    f"Hacker News hiring connector raised an unexpected error and was skipped: "
                    f"{type(hn_exc).__name__}: {hn_exc}"
                )
            finally:
                try:
                    # Release the HTTP client on the loop that owns it.
                    loop.run_until_complete(hn_connector.close())
                except Exception:  # noqa: BLE001 - cleanup must never matter
                    pass

            # Try YC directory (CSV import if configured)
            yc_connector = get_yc_connector()
            yc_result = loop.run_until_complete(yc_connector.discover(query))
            connector_results.append(("yc", yc_result))
            if yc_result.is_success() and yc_result.candidates:
                all_candidates.extend(("yc", c) for c in yc_result.candidates)

            # Try Brave (fixture fallback)
            brave_connector = get_brave_connector()
            brave_result = loop.run_until_complete(brave_connector.discover(query))
            connector_results.append(("brave", brave_result))
            if brave_result.is_success() and brave_result.candidates:
                all_candidates.extend(("brave", c) for c in brave_result.candidates)
        finally:
            loop.close()

        # Deduplicate by domain
        seen_domains = set()
        unique_candidates = []  # (provider_name, candidate)
        for provider_name, candidate in all_candidates:
            domain = candidate.normalized_domain()
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                unique_candidates.append((provider_name, candidate))
            elif not domain and candidate.name not in [c.name for _, c in unique_candidates]:
                # No domain but unique name - keep
                unique_candidates.append((provider_name, candidate))

        # Limit to max_results
        candidates = unique_candidates[:query.max_results]

        # Per-candidate provenance: each candidate carries the connector that
        # produced it, so source records can be attributed honestly.
        results_by_name = dict(connector_results)

        # Determine overall status and primary connector for reporting
        live_results = [r for name, r in connector_results if name in ("tavily", "exa", "remoteok", "hn") and r.is_success()]
        if live_results:
            # Use first live connector with results as primary
            primary = next((c for c in connector_results if c[1].candidates), None)
            connector = primary[1] if primary else None
            connector_status = connector.status.value if connector else "unknown"
        else:
            # Fall back to first connector
            connector = connector_results[0][1] if connector_results else brave_result
            connector_status = connector.status.value if connector else "unknown"

        error_code = None
        error_message = None
        # HN is best-effort: a failure there is recorded, but does not stop discovery.
        for name, result in connector_results:
            if result.status == ConnectorStatus.FAILED and name != "hn":
                error_code = result.error_code
                error_message = result.error_message
                break

        findings: list[str] = []
        event_details: dict[str, Any] = {
            "discovery_connectors": [name for name, _ in connector_results],
            "connector_statuses": {name: result.status.value for name, result in connector_results},
            "candidates_returned": len(candidates),
            "query": {
                "countries": query.countries,
                "sectors": query.sectors,
                "employee_min": query.employee_min,
                "employee_max": query.employee_max,
            },
        }

        # Best-effort HN notes: keep the event honestly degraded instead of failing.
        if event_details["connector_statuses"].get("hn") == ConnectorStatus.FAILED.value:
            hn_notes.append(
                "Hacker News hiring connector is currently unavailable — discovery "
                "continued with the remaining sources."
            )
        if hn_notes:
            event_details["hn_notes"] = hn_notes
            findings.extend(hn_notes)

        if error_code:
            findings.append(
                f"Discovery failed: {error_code or 'unknown_error'} — {error_message or 'no details'}"
            )
            event_details["error_code"] = error_code
            event_details["error_message"] = error_message
            return {
                "stage": "find",
                "outcome": "stopped_after_error",
                "error_code": error_code or "discovery_failed",
                "error": error_message or "Discovery connector failed",
                "findings": findings,
                "_event_status": "failed",
                "_event_details": event_details,
            }

        if connector is not None and connector.status == ConnectorStatus.NOT_CONFIGURED:
            findings.append(
                f"Discovery connector {connector.provider} is not configured. "
                "Running in fixture mode with example candidates."
            )
            event_details["fixture_mode"] = True

        if connector is not None and connector.status == ConnectorStatus.SUCCESS_EMPTY and not candidates:
            findings.append("Discovery returned no candidates for the given criteria.")
            event_details["empty_results"] = True

        if candidates:
            findings.append(f"Discovery returned {len(candidates)} candidate companies.")
            if connector is not None and connector.status == ConnectorStatus.NOT_CONFIGURED:
                event_details["fixture_mode"] = True

        # Persist candidates as companies and source records
        created_companies = []
        duplicate_companies = []

        with session_scope() as db:
            for provider_name, candidate in candidates:
                domain = candidate.normalized_domain()
                # The connector result that produced THIS candidate.
                candidate_result = results_by_name.get(provider_name)
                provider_label = (
                    candidate_result.provider if candidate_result is not None else provider_name
                )

                # Check for existing company with same domain in this campaign
                existing = None
                if domain:
                    existing = (
                        db.query(Company)
                        .filter(
                            Company.campaign_id == campaign_id,
                            Company.website_domain == domain,
                        )
                        .first()
                    )

                if existing:
                    duplicate_companies.append(
                        {
                            "candidate_name": candidate.name,
                            "existing_company_id": existing.id,
                            "existing_company_name": existing.canonical_name,
                            "domain": domain,
                        }
                    )
                    # Add source record to existing company
                    db.add(
                        SourceRecord(
                            company_id=existing.id,
                            source_type="discovery",
                            provider=provider_label,
                            source_url=candidate.source_url,
                            retrieved_at=candidate_result.retrieved_at,
                            raw_payload_json=_dump(
                                {
                                    "candidate_name": candidate.name,
                                    "snippet": candidate.snippet,
                                    "provider_meta": candidate.provider_meta,
                                }
                            ),
                            status="success_with_results",
                        )
                    )
                else:
                    # Create new company
                    normalized_name = candidate.name.strip().lower()
                    company = Company(
                        campaign_id=campaign_id,
                        canonical_name=candidate.name,
                        normalized_name=normalized_name,
                        website_domain=domain,
                        country=candidate.country,
                        sector=candidate.sector,
                        employee_min=candidate.employee_min,
                        employee_max=candidate.employee_max,
                        record_kind="retrieved",
                        workflow_status="discovered",
                    )
                    db.add(company)
                    db.flush()

                    # Add source record
                    db.add(
                        SourceRecord(
                            company_id=company.id,
                            source_type="discovery",
                            provider=provider_label,
                            source_url=candidate.source_url,
                            retrieved_at=candidate_result.retrieved_at,
                            raw_payload_json=_dump(
                                {
                                    "candidate_name": candidate.name,
                                    "snippet": candidate.snippet,
                                    "provider_meta": candidate.provider_meta,
                                }
                            ),
                            status="success_with_results",
                        )
                    )
                    created_companies.append(
                        {
                            "id": company.id,
                            "name": company.canonical_name,
                            "domain": domain,
                        }
                    )

        if duplicate_companies:
            findings.append(
                f"{len(duplicate_companies)} candidate(s) matched existing companies by domain."
            )
            event_details["duplicates"] = duplicate_companies

        if created_companies:
            findings.append(f"Created {len(created_companies)} new company record(s).")
            event_details["created_companies"] = created_companies

        # For discovery runs, we don't have a single company_id upfront.
        # The run tracks the campaign and creates multiple companies.
        # We store the first created company's ID for compatibility, or 0 if none.
        first_company_id = created_companies[0]["id"] if created_companies else 0

        # Determine outcome — discovery runs always continue; qualification, not
        # connector success/failure, decides the next routing step.
        outcome = "continue"

        return {
            "stage": "find",
            "outcome": outcome,
            "findings": findings,
            "company_id": first_company_id,
            "created_company_ids": [c["id"] for c in created_companies],
            "_event_status": "ok",
            "_event_details": event_details,
        }

    else:
        # Qualification run: single company already exists
        record_kind = state.get("record_kind", "test_seed")

        if record_kind == "test_seed":
            finding = (
                "Discovery connectors are not configured in Milestone 1. "
                "This record was entered manually and is labelled as TEST DATA."
            )
        else:
            finding = "Record produced by a source connector (see source_records)."

        if state.get("website_domain"):
            finding += f" Candidate domain: {state['website_domain']}."

        # Provenance: an explicit, honest record that discovery did not run.
        if state.get("company_id"):
            with session_scope() as db:
                existing = (
                    db.query(Company)
                    .filter(
                        Company.id == state["company_id"],
                    )
                    .first()
                )
                if existing is not None:

                    already = (
                        db.query(SourceRecord)
                        .filter(
                            SourceRecord.company_id == state["company_id"],
                            SourceRecord.source_type == "discovery",
                        )
                        .first()
                    )
                    if already is None:
                        db.add(
                            SourceRecord(
                                company_id=state["company_id"],
                                source_type="discovery",
                                provider="none",
                                status="not_configured",
                                source_url=None,
                                raw_payload_json=_dump(
                                    {
                                        "note": "No discovery connector is enabled in Milestone 1.",
                                        "record_kind": record_kind,
                                    }
                                ),
                            )
                        )

        return {
            "stage": "find",
            "outcome": "continue",
            "findings": [finding],
            "_event_details": {"discovery_connectors": [], "status": "not_configured"},
        }


@_stage("merge")
def merge_node(state: GraphState) -> dict[str, Any]:
    """Duplicate check: one real company must become one record."""
    domain = (state.get("website_domain") or "").strip().lower()
    if not domain:
        return {
            "stage": "merge",
            "outcome": "continue",
            "findings": ["No domain supplied, so duplicate matching is not possible yet."],
            "_event_details": {"duplicates_found": 0},
        }

    with session_scope() as db:
        duplicates = (
            db.query(Company)
            .filter(
                Company.campaign_id == state.get("campaign_id"),
                Company.website_domain == domain,
                Company.id != state.get("company_id"),
            )
            .all()
        )

    if duplicates:
        names = ", ".join(f"'{d.canonical_name}' (id {d.id})" for d in duplicates)
        reason = (
            f"Duplicate candidate: domain '{domain}' already exists as {names}. "
            "Records must be merged by a human before this one can advance."
        )
        return {
            "stage": "merge",
            "outcome": "needs_human_review",
            "review_reason": reason,
            "findings": [reason],
            "_event_status": "held_for_review",
            "_event_details": {
                "duplicates_found": len(duplicates),
                "duplicate_ids": [d.id for d in duplicates],
            },
        }

    return {
        "stage": "merge",
        "outcome": "continue",
        "findings": [f"No duplicate found for domain '{domain}'."],
        "_event_details": {"duplicates_found": 0},
    }


def _check(rule: str, status: str, detail: str) -> dict[str, str]:
    return {"rule": rule, "status": status, "detail": detail}


def qualify(record: dict[str, Any], settings: dict[str, Any]) -> list[dict[str, str]]:
    """Deterministic target-fit checks. Unknown never counts as a match."""
    checks: list[dict[str, str]] = []

    countries = [str(c).strip().lower() for c in settings.get("countries", []) if str(c).strip()]
    if countries:
        value = (record.get("country") or "").strip()
        if not value:
            checks.append(_check("country", "unknown", "Company country is not set."))
        elif value.lower() in countries:
            checks.append(_check("country", "pass", f"Country '{value}' is in the campaign list."))
        else:
            checks.append(_check("country", "fail", f"Country '{value}' is not in the campaign list."))

    keywords = [str(k).strip().lower() for k in settings.get("sectors", []) if str(k).strip()]
    if keywords:
        value = (record.get("sector") or "").strip()
        if not value:
            checks.append(_check("sector", "unknown", "Company sector is not set."))
        elif any(k in value.lower() for k in keywords):
            checks.append(_check("sector", "pass", f"Sector '{value}' matches a campaign keyword."))
        else:
            checks.append(_check("sector", "fail", f"Sector '{value}' matches no campaign keyword."))

    c_min = settings.get("employee_min")
    c_max = settings.get("employee_max")
    if c_min is not None or c_max is not None:
        r_min = record.get("employee_min")
        r_max = record.get("employee_max")
        if r_min is None or r_max is None or c_min is None or c_max is None:
            checks.append(
                _check(
                    "employee_range",
                    "unknown",
                    "Employee range is incomplete on the campaign or the company record.",
                )
            )
        elif r_max >= c_min and r_min <= c_max:
            checks.append(
                _check(
                    "employee_range",
                    "pass",
                    f"{r_min}-{r_max} employees overlaps the campaign range {c_min}-{c_max}.",
                )
            )
        else:
            checks.append(
                _check(
                    "employee_range",
                    "fail",
                    f"{r_min}-{r_max} employees does not overlap {c_min}-{c_max}.",
                )
            )

    if settings.get("require_domain", True):
        if record.get("website_domain"):
            checks.append(_check("website_domain", "pass", "A website domain is present."))
        else:
            checks.append(
                _check("website_domain", "unknown", "No website domain, so facts cannot be evidenced.")
            )

    return checks


@_stage("evaluate")
def evaluate_node(state: GraphState) -> dict[str, Any]:
    checks = qualify(
        {
            "country": state.get("country"),
            "sector": state.get("sector"),
            "employee_min": state.get("employee_min"),
            "employee_max": state.get("employee_max"),
            "website_domain": state.get("website_domain"),
        },
        state.get("settings") or {},
    )

    statuses = {c["status"] for c in checks}
    reasons = [f"{c['rule']}: {c['detail']}" for c in checks if c["status"] in {"unknown", "conflict"}]
    failures = [f"{c['rule']}: {c['detail']}" for c in checks if c["status"] == "fail"]

    if not checks:
        outcome = "needs_human_review"
        decision = "needs_review"
        review_reason = "No campaign rules are configured, so target fit cannot be decided."
    elif "unknown" in statuses or "conflict" in statuses:
        outcome = "needs_human_review"
        decision = "needs_review"
        review_reason = " ".join(reasons)
    elif failures:
        outcome = "rejected"
        decision = "rejected"
        review_reason = None
    else:
        outcome = "continue"
        decision = "qualified"
        review_reason = None

    return {
        "stage": "evaluate",
        "outcome": outcome,
        "decision": decision,
        "checks": checks,
        "review_reason": review_reason,
        "_event_status": "held_for_review" if outcome == "needs_human_review" else "ok",
        "_event_details": {"checks": checks, "decision": decision},
    }


@_stage("hold_for_review")
def hold_for_review_node(state: GraphState) -> dict[str, Any]:
    return {
        "stage": "hold_for_review",
        "outcome": state.get("outcome") or "needs_human_review",
        "_event_status": "held_for_review",
        "_event_details": {"reason": state.get("review_reason")},
    }


@_stage("reject")
def reject_node(state: GraphState) -> dict[str, Any]:
    return {
        "stage": "reject",
        "outcome": "rejected",
        "_event_details": {"checks": state.get("checks")},
    }


@_stage("finish")
def finish_node(state: GraphState) -> dict[str, Any]:
    # Preserve meaningful outcomes (like needs_human_review) from upstream
    outcome = state.get("outcome")
    if outcome in ("needs_human_review", "rejected", "stopped_after_error"):
        final_outcome = outcome
    else:
        final_outcome = outcome or "continue"
    
    return {
        "stage": "finish",
        "outcome": final_outcome,
        "decision": state.get("decision") or "qualified",
        "_event_details": {"decision": state.get("decision")},
    }


@_stage("stop_after_error")
def stop_after_error_node(state: GraphState) -> dict[str, Any]:
    return {
        "stage": "stop_after_error",
        "outcome": "stopped_after_error",
        "_event_status": "failed",
        "_event_details": {
            "error_code": state.get("error_code"),
            "error": state.get("error"),
            "record_advanced": False,
        },
    }


# --- research ----------------------------------------------------------------


@_stage("research")
def research_node(state: GraphState) -> dict[str, Any]:
    """Generate evidence-backed research brief for the company."""
    company_id = state.get("company_id")
    campaign_id = state.get("campaign_id")

    if not company_id:
        return {
            "stage": "research",
            "outcome": "stopped_after_error",
            "error_code": "missing_company_id",
            "error": "No company ID for research",
            "findings": ["No company ID available for research"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    from .models import Company, Campaign
    from .db import session_scope

    with session_scope() as db:
        company = db.get(Company, company_id)
        campaign = db.get(Campaign, campaign_id) if campaign_id else None

    if not company:
        return {
            "stage": "research",
            "outcome": "stopped_after_error",
            "error_code": "company_not_found",
            "error": f"Company {company_id} not found",
            "findings": [f"Company {company_id} not found in database"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "company_not_found"},
        }

    # Generate research brief
    try:
        brief = generate_research_brief(company, campaign)
    except Exception as e:
        return {
            "stage": "research",
            "outcome": "stopped_after_error",
            "error_code": "research_generation_failed",
            "error": f"Failed to generate research brief: {e}",
            "findings": [f"Research generation failed: {e}"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "generation_failed"},
        }

    # Persist brief to company record
    with session_scope() as db:
        company = db.get(Company, company_id)
        if company:
            company.research_brief = brief
            company.research_generated_at = utcnow()
            company.research_model_version = 1
            db.commit()

    return {
        "stage": "research",
        "outcome": "continue",
        "findings": ["Research brief generated successfully"],
        "_event_status": "ok",
        "_event_details": {"brief_length": len(brief)},
    }


# --- approval ----------------------------------------------------------------


@_stage("approval")
def approval_node(state: GraphState) -> dict[str, Any]:
    """Approval gate - waits for human decision or uses existing approval status."""
    company_id = state.get("company_id")

    if not company_id:
        return {
            "stage": "approval",
            "outcome": "stopped_after_error",
            "error_code": "missing_company_id",
            "error": "No company ID for approval",
            "findings": ["No company ID available for approval"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    from .models import Company
    from .db import session_scope

    with session_scope() as db:
        company = db.get(Company, company_id)

    if not company:
        return {
            "stage": "approval",
            "outcome": "stopped_after_error",
            "error_code": "company_not_found",
            "error": f"Company {company_id} not found",
            "findings": [f"Company {company_id} not found in database"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "company_not_found"},
        }

    # Check existing approval status
    approval_status = company.approval_status

    if approval_status == "approved":
        return {
            "stage": "approval",
            "outcome": "continue",
            "findings": ["Lead already approved for outreach"],
            "_event_status": "ok",
            "_event_details": {"approval_status": "approved", "approved_at": company.approved_at},
        }
    elif approval_status == "rejected":
        return {
            "stage": "approval",
            "outcome": "rejected",
            "findings": ["Lead rejected during review"],
            "_event_status": "ok",
            "_event_details": {"approval_status": "rejected", "approved_at": company.approved_at},
        }
    else:
        # No decision yet - hold for human review
        return {
            "stage": "approval",
            "outcome": "needs_human_review",
            "review_reason": "Awaiting human approval decision",
            "findings": ["Lead requires human approval before outreach"],
            "_event_status": "held_for_review",
            "_event_details": {"approval_status": "pending"},
        }


# --- dry_run ----------------------------------------------------------------


@_stage("dry_run")
def dry_run_node(state: GraphState) -> dict[str, Any]:
    """Dry-run safety gate - simulates outreach without sending.

    Always returns blocked because DRY_RUN=true is enforced.
    """
    from .safety import evaluate_outreach, Channel, is_dry_run

    company_id = state.get("company_id")
    campaign_id = state.get("campaign_id")

    if not company_id:
        return {
            "stage": "dry_run",
            "outcome": "stopped_after_error",
            "error_code": "missing_company_id",
            "error": "No company ID for dry run",
            "findings": ["No company ID available for dry run"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    # Check approval status
    from .models import Company
    from .db import session_scope

    with session_scope() as db:
        company = db.get(Company, company_id)
        campaign = db.get(Campaign, campaign_id) if state.get("campaign_id") else None

    if not company:
        return {
            "stage": "dry_run",
            "outcome": "stopped_after_error",
            "error_code": "company_not_found",
            "error": f"Company {company_id} not found",
            "findings": [f"Company {company_id} not found in database"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "company_not_found"},
        }

    if company.approval_status != "approved":
        return {
            "stage": "dry_run",
            "outcome": "stopped_after_error",
            "error_code": "not_approved",
            "error": "Lead not approved for outreach",
            "findings": ["Lead must be approved before dry run"],
            "_event_status": "failed",
            "_event_details": {"approval_status": company.approval_status},
        }

    # Check exclusions
    if company.is_excluded:
        return {
            "stage": "dry_run",
            "outcome": "stopped_after_error",
            "error_code": "excluded",
            "error": f"Lead excluded: {company.exclusion_reason}",
            "findings": [f"Lead excluded: {company.exclusion_reason}"],
            "_event_status": "failed",
            "_event_details": {"exclusion_reason": company.exclusion_reason},
        }

    # Run safety evaluation for each channel
    channels = [Channel.EMAIL, Channel.SMS, Channel.LINKEDIN, Channel.SOCIAL, Channel.WEBSITE_FORM]
    results = []
    all_blocked = True

    for channel in channels:
        result = evaluate_outreach(channel, approved=True)
        results.append({
            "channel": result.channel,
            "would_send": result.would_send,
            "result": result.result,
            "reason": result.reason,
            "dry_run": result.dry_run,
        })
        if result.result == "WOULD_PASS":
            all_blocked = False

    # In DRY_RUN mode, all channels should be BLOCKED
    return {
        "stage": "dry_run",
        "outcome": "stopped_after_error" if all_blocked else "continue",
        "findings": [
            f"DRY_RUN mode: no messages sent",
            f"Channels evaluated: {len(channels)}",
            f"All blocked by dry-run guard: {all_blocked}",
        ],
        "_event_status": "ok",
        "_event_details": {
            "dry_run": True,
            "channels": results,
            "safety_banner": "DRY RUN — NO MESSAGES SENT",
        },
    }


# --- routing ---------------------------------------------------------------


def _route_after_start(state: GraphState) -> Literal["stop_after_error", "find"]:
    return "stop_after_error" if state.get("outcome") == "stopped_after_error" else "find"


def _route_after_find(state: GraphState) -> Literal["stop_after_error", "merge", "finish"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    if state.get("run_type") == "discovery":
        # Discovery runs complete after the find stage
        return "finish"
    return "merge"


def _route_after_merge(state: GraphState) -> Literal["stop_after_error", "hold_for_review", "evaluate"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    if state.get("review_reason"):
        return "hold_for_review"
    return "evaluate"


# --- enrichment nodes --------------------------------------------------------


def _enrichment_ok(result) -> bool:
    """Enrichment is only fatal on real provider failure.

    NOT_CONFIGURED / UNSUPPORTED are honest, expected states: the app must stay
    usable without API keys, so those continue the pipeline with the status
    recorded in the event details. Only FAILED stops the run.
    """
    return result.status in (
        ConnectorStatus.SUCCESS_WITH_RESULTS,
        ConnectorStatus.SUCCESS_EMPTY,
        ConnectorStatus.NOT_CONFIGURED,
        ConnectorStatus.UNSUPPORTED,
    )


@_stage("website_enrichment")
def website_enrichment_node(state: GraphState) -> dict[str, Any]:
    """Enrich company using website fetcher."""
    company_id = state.get("company_id")
    if not company_id:
        return {
            "stage": "website_enrichment",
            "outcome": "continue",
            "findings": ["No company ID for enrichment"],
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    connector = get_website_connector()
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(connector.enrich([company_id], EnrichmentQuery(
            campaign_id=state.get("campaign_id"),
            company_ids=[company_id],
            domains=[state.get("website_domain")] if state.get("website_domain") else [],
            names=[state.get("company_name")],
        )))
    finally:
        loop.close()

    findings = [f"Website enrichment: {result.status.value}"]
    if result.candidates:
        findings.append(f"Enriched {len(result.candidates)} fields")

    return {
        "stage": "website_enrichment",
        "outcome": "continue" if _enrichment_ok(result) else "stopped_after_error",
        "findings": findings,
        "error_code": result.error_code,
        "error": result.error_message,
        "_event_status": "ok" if _enrichment_ok(result) else "failed",
        "_event_details": {
            "connector": "website",
            "status": result.status.value,
            "candidates": len(result.candidates),
        },
    }


@_stage("jobs_enrichment")
def jobs_enrichment_node(state: GraphState) -> dict[str, Any]:
    """Enrich company using Greenhouse job postings."""
    company_id = state.get("company_id")
    if not company_id:
        return {
            "stage": "jobs_enrichment",
            "outcome": "continue",
            "findings": ["No company ID for enrichment"],
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    connector = get_greenhouse_connector()
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(connector.enrich([company_id], EnrichmentQuery(
            campaign_id=state.get("campaign_id"),
            company_ids=[company_id],
            domains=[state.get("website_domain")] if state.get("website_domain") else [],
            names=[state.get("company_name")],
        )))
    finally:
        loop.close()

    findings = [f"Jobs enrichment: {result.status.value}"]
    if result.candidates:
        findings.append(f"Found {len(result.candidates)} job postings")

    return {
        "stage": "jobs_enrichment",
        "outcome": "continue" if _enrichment_ok(result) else "stopped_after_error",
        "findings": findings,
        "error_code": result.error_code,
        "error": result.error_message,
        "_event_status": "ok" if _enrichment_ok(result) else "failed",
        "_event_details": {
            "connector": "greenhouse",
            "status": result.status.value,
            "candidates": len(result.candidates),
        },
    }


@_stage("news_enrichment")
def news_enrichment_node(state: GraphState) -> dict[str, Any]:
    """Enrich company using GNews."""
    company_id = state.get("company_id")
    if not company_id:
        return {
            "stage": "news_enrichment",
            "outcome": "continue",
            "findings": ["No company ID for enrichment"],
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    connector = get_gnews_connector()
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(connector.enrich([company_id], EnrichmentQuery(
            campaign_id=state.get("campaign_id"),
            company_ids=[company_id],
            domains=[state.get("website_domain")] if state.get("website_domain") else [],
            names=[state.get("company_name")],
        )))
    finally:
        loop.close()

    findings = [f"News enrichment: {result.status.value}"]
    if result.candidates:
        findings.append(f"Found {len(result.candidates)} articles")

    return {
        "stage": "news_enrichment",
        "outcome": "continue" if _enrichment_ok(result) else "stopped_after_error",
        "findings": findings,
        "error_code": result.error_code,
        "error": result.error_message,
        "_event_status": "ok" if _enrichment_ok(result) else "failed",
        "_event_details": {
            "connector": "gnews",
            "status": result.status.value,
            "candidates": len(result.candidates),
        },
    }


@_stage("sec_enrichment")
def sec_enrichment_node(state: GraphState) -> dict[str, Any]:
    """Enrich company using SEC EDGAR."""
    company_id = state.get("company_id")
    if not company_id:
        return {
            "stage": "sec_enrichment",
            "outcome": "continue",
            "findings": ["No company ID for enrichment"],
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    connector = get_sec_connector()
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(connector.enrich([company_id], EnrichmentQuery(
            campaign_id=state.get("campaign_id"),
            company_ids=[company_id],
            domains=[state.get("website_domain")] if state.get("website_domain") else [],
            names=[state.get("company_name")],
        )))
    finally:
        loop.close()

    findings = [f"SEC enrichment: {result.status.value}"]
    if result.candidates:
        findings.append(f"Found {len(result.candidates)} filings")

    return {
        "stage": "sec_enrichment",
        "outcome": "continue" if _enrichment_ok(result) else "stopped_after_error",
        "findings": findings,
        "error_code": result.error_code,
        "error": result.error_message,
        "_event_status": "ok" if _enrichment_ok(result) else "failed",
        "_event_details": {
            "connector": "sec",
            "status": result.status.value,
            "candidates": len(result.candidates),
        },
    }


@_stage("opencorporates_enrichment")
def opencorporates_enrichment_node(state: GraphState) -> dict[str, Any]:
    """Enrich company using OpenCorporates."""
    company_id = state.get("company_id")
    if not company_id:
        return {
            "stage": "opencorporates_enrichment",
            "outcome": "continue",
            "findings": ["No company ID for enrichment"],
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    connector = get_opencorporates_connector()
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(connector.enrich([company_id], EnrichmentQuery(
            campaign_id=state.get("campaign_id"),
            company_ids=[company_id],
            domains=[state.get("website_domain")] if state.get("website_domain") else [],
            names=[state.get("company_name")],
        )))
    finally:
        loop.close()

    findings = [f"OpenCorporates enrichment: {result.status.value}"]
    if result.candidates:
        findings.append(f"Found {len(result.candidates)} records")

    # Only treat FAILED as error; NOT_CONFIGURED/SUCCESS_EMPTY continue normally
    is_failed = result.status == ConnectorStatus.FAILED

    return {
        "stage": "opencorporates_enrichment",
        "outcome": "continue" if _enrichment_ok(result) else "stopped_after_error",
        "findings": findings,
        "error_code": result.error_code if is_failed else None,
        "error": result.error_message if is_failed else None,
        "_event_status": "ok" if _enrichment_ok(result) else "failed",
        "_event_details": {
            "connector": "opencorporates",
            "status": result.status.value,
            "candidates": len(result.candidates),
        },
    }


# --- scoring ---------------------------------------------------------------


@_stage("scoring")
def scoring_node(state: GraphState) -> dict[str, Any]:
    """Scoring and qualification stage - deterministic 0-100 score with factor breakdown."""
    company_id = state.get("company_id")
    campaign_id = state.get("campaign_id")

    if not company_id:
        return {
            "stage": "scoring",
            "outcome": "stopped_after_error",
            "error_code": "missing_company_id",
            "error": "No company ID for scoring",
            "findings": ["No company ID available for scoring"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "no_company_id"},
        }

    # Load company and campaign from DB
    from .models import Company, Campaign
    from .db import session_scope

    with session_scope() as db:
        company = db.get(Company, company_id)
        campaign = db.get(Campaign, campaign_id)

    if not company:
        return {
            "stage": "scoring",
            "outcome": "stopped_after_error",
            "error_code": "company_not_found",
            "error": f"Company {company_id} not found",
            "findings": [f"Company {company_id} not found in database"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "company_not_found"},
        }

    if not campaign:
        return {
            "stage": "scoring",
            "outcome": "stopped_after_error",
            "error_code": "campaign_not_found",
            "error": f"Campaign {campaign_id} not found",
            "findings": [f"Campaign {campaign_id} not found in database"],
            "_event_status": "failed",
            "_event_details": {"skipped": True, "reason": "campaign_not_found"},
        }

    # Run deterministic scoring
    from .scoring import score_company
    result: ScoreResult = score_company(company, campaign)

    # Persist score to company record
    with session_scope() as db:
        company = db.get(Company, company_id)
        if company:
            company.lead_fit_score = result.total_score
            company.evidence_confidence = result.confidence
            company.qualification_status = result.qualification_status
            company.qualification_reason = result.qualification_reason
            company.scoring_version = result.scoring_version
            company.scored_at = result.scored_at
            company.is_excluded = bool(result.hard_exclusions)
            company.exclusion_reason = "; ".join(result.hard_exclusions) if result.hard_exclusions else None
            db.commit()

    # Determine outcome
    if result.hard_exclusions:
        outcome = "rejected"
    elif result.qualification_status == "needs_review":
        outcome = "needs_human_review"
    elif result.qualification_status == "rejected":
        outcome = "rejected"
    else:
        outcome = "continue"

    return {
        "stage": "scoring",
        "outcome": outcome,
        "findings": [
            f"Lead fit score: {result.total_score}/100",
            f"Evidence confidence: {result.confidence}/100",
            f"Qualification: {result.qualification_status}",
            *[f"  - {f.name}: {f.earned_points}/{f.max_points} - {f.explanation}" for f in result.factors],
        ] + ([result.qualification_reason] if result.qualification_reason else []),
        "checks": [
            {"factor": f.name, "earned": f.earned_points, "max": f.max_points, "explanation": f.explanation}
            for f in result.factors
        ],
        "score_breakdown": {
            "total_score": result.total_score,
            "confidence": result.confidence,
            "qualification": result.qualification_status,
            "requires_review": result.requires_human_review,
        },
        "_event_status": "held_for_review" if result.qualification_status == "needs_review" else ("failed" if result.hard_exclusions else "ok"),
        "_event_details": {
            "score_breakdown": {
                "total_score": result.total_score,
                "confidence": result.confidence,
                "qualification": result.qualification_status,
                "requires_review": result.requires_human_review,
            },
            "hard_exclusions": result.hard_exclusions,
            "factors": [
                {"name": f.name, "earned": f.earned_points, "max": f.max_points, "explanation": f.explanation}
                for f in result.factors
            ],
        },
    }


# --- routing ---------------------------------------------------------------


def _route_after_evaluate(
    state: GraphState,
) -> Literal["finish", "hold_for_review", "reject", "stop_after_error", "website_enrichment", "scoring"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    outcome = state.get("outcome")
    if state.get("run_type") in ("enrichment", "qualification"):
        # Hard rejection (country mismatch etc.) → stop
        if outcome == "rejected":
            return "reject"
        # Missing required facts or unresolvable conflict → hold for human review, stop pipeline
        if outcome == "needs_human_review":
            return "hold_for_review"
        # Clear pass (continue) → proceed through enrichment, scoring, research, approval
        return "website_enrichment"
    # Default path for other run types
    return {
        "continue": "scoring",
        "needs_human_review": "hold_for_review",
        "rejected": "reject",
    }.get(outcome, "hold_for_review")


def _route_after_scoring(state: GraphState) -> Literal["stop_after_error", "research"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    # For qualification runs, go to research after scoring
    if state.get("run_type") == "qualification":
        return "research"
    return "finish"


def _route_after_website(state: GraphState) -> Literal["stop_after_error", "jobs_enrichment"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    return "jobs_enrichment"


def _route_after_jobs(state: GraphState) -> Literal["stop_after_error", "news_enrichment"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    return "news_enrichment"


def _route_after_news(state: GraphState) -> Literal["stop_after_error", "sec_enrichment"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    return "sec_enrichment"


def _route_after_sec(state: GraphState) -> Literal["stop_after_error", "opencorporates_enrichment"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    return "opencorporates_enrichment"


def _route_after_opencorporates(state: GraphState) -> Literal["stop_after_error", "finish", "scoring"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    # For qualification runs, go to scoring after opencorporates
    if state.get("run_type") == "qualification":
        return "scoring"
    return "finish"


def _route_after_approval(state: GraphState) -> Literal["stop_after_error", "dry_run", "finish"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    # If approved (continue), go to dry_run; if needs_human_review or rejected, finish
    if state.get("outcome") == "continue":
        return "dry_run"
    return "finish"


def _route_after_dry_run(state: GraphState) -> Literal["stop_after_error", "finish"]:
    if state.get("outcome") == "stopped_after_error":
        return "stop_after_error"
    return "finish"


def build_graph():
    """Compile the workflow graph."""
    graph = StateGraph(GraphState)
    graph.add_node("start", start_node)
    graph.add_node("find", find_node)
    graph.add_node("merge", merge_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("hold_for_review", hold_for_review_node)
    graph.add_node("reject", reject_node)
    graph.add_node("finish", finish_node)
    graph.add_node("stop_after_error", stop_after_error_node)
    graph.add_node("website_enrichment", website_enrichment_node)
    graph.add_node("jobs_enrichment", jobs_enrichment_node)
    graph.add_node("news_enrichment", news_enrichment_node)
    graph.add_node("sec_enrichment", sec_enrichment_node)
    graph.add_node("opencorporates_enrichment", opencorporates_enrichment_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("research", research_node)
    graph.add_node("approval", approval_node)
    graph.add_node("dry_run", dry_run_node)

    graph.add_edge(START, "start")
    graph.add_conditional_edges(
        "start", _route_after_start, {"stop_after_error": "stop_after_error", "find": "find"}
    )
    graph.add_conditional_edges(
        "find", _route_after_find, {"stop_after_error": "stop_after_error", "merge": "merge", "finish": "finish"}
    )
    graph.add_conditional_edges(
        "merge",
        _route_after_merge,
        {"stop_after_error": "stop_after_error", "hold_for_review": "hold_for_review", "evaluate": "evaluate"},
    )
    graph.add_conditional_edges(
        "evaluate",
        _route_after_evaluate,
        {
            "finish": "finish",
            "hold_for_review": "hold_for_review",
            "reject": "reject",
            "stop_after_error": "stop_after_error",
            "website_enrichment": "website_enrichment",
            "scoring": "scoring",
        },
    )
    graph.add_conditional_edges(
        "website_enrichment", _route_after_website, {"stop_after_error": "stop_after_error", "jobs_enrichment": "jobs_enrichment"}
    )
    graph.add_conditional_edges(
        "jobs_enrichment", _route_after_jobs, {"stop_after_error": "stop_after_error", "news_enrichment": "news_enrichment"}
    )
    graph.add_conditional_edges(
        "news_enrichment", _route_after_news, {"stop_after_error": "stop_after_error", "sec_enrichment": "sec_enrichment"}
    )
    graph.add_conditional_edges(
        "sec_enrichment", _route_after_sec, {"stop_after_error": "stop_after_error", "opencorporates_enrichment": "opencorporates_enrichment"}
    )
    graph.add_conditional_edges(
        "opencorporates_enrichment", _route_after_opencorporates, {"stop_after_error": "stop_after_error", "finish": "finish", "scoring": "scoring"}
    )
    graph.add_conditional_edges(
        "scoring",
        _route_after_scoring,
        {"stop_after_error": "stop_after_error", "research": "research", "finish": "finish"},
    )
    # Research -> Approval -> Dry Run chain
    graph.add_edge("research", "approval")
    graph.add_conditional_edges(
        "approval",
        _route_after_approval,
        {"stop_after_error": "stop_after_error", "dry_run": "dry_run", "finish": "finish"},
    )
    graph.add_conditional_edges(
        "dry_run",
        _route_after_dry_run,
        {"stop_after_error": "stop_after_error", "finish": "finish"},
    )
    graph.add_edge("finish", END)

    return graph.compile()


_COMPILED = None


def get_graph():
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_graph()
    return _COMPILED


# --- runner ----------------------------------------------------------------

RUN_STATUS_BY_OUTCOME = {
    "continue": "completed",
    "needs_human_review": "needs_review",
    "rejected": "rejected",
    "stopped_after_error": "failed",
}


def load_graph_state(run_id: int, fail_at: str | None = None) -> GraphState:
    """Build the initial graph state for an existing run row."""
    from .models import Campaign

    with session_scope() as db:
        run = db.get(WorkflowRun, run_id)
        if run is None:
            raise ValueError(f"Workflow run {run_id} not found")
        company = db.get(Company, run.company_id) if run.company_id else None
        campaign = db.get(Campaign, run.campaign_id)

        return GraphState(
            run_id=run.id,
            campaign_id=run.campaign_id,
            company_id=company.id if company else 0,
            company_name=company.canonical_name if company else "",
            record_kind=company.record_kind if company else "test_seed",
            website_domain=company.website_domain if company else None,
            country=company.country if company else None,
            sector=company.sector if company else None,
            employee_min=company.employee_min if company else None,
            employee_max=company.employee_max if company else None,
            settings=campaign.settings if campaign else {},
            fail_at=fail_at,
            run_type=run.run_type,
            created_company_ids=[],
            stage="",
            outcome=None,
            decision=None,
            findings=[],
            checks=[],
            review_reason=None,
            error_code=None,
            error=None,
        )


def run_workflow(run_id: int, fail_at: str | None = None) -> dict[str, Any]:
    """Execute the graph for a stored run and persist the final outcome."""
    state = load_graph_state(run_id, fail_at=fail_at)
    try:
        final: dict[str, Any] = get_graph().invoke(state)
    except Exception as exc:  # pragma: no cover - graph nodes already trap errors
        final = {
            "outcome": "stopped_after_error",
            "error_code": "graph_failure",
            "error": f"{type(exc).__name__}: {exc}",
        }

    outcome = final.get("outcome") or "stopped_after_error"
    status = RUN_STATUS_BY_OUTCOME.get(outcome, "failed")

    with session_scope() as db:
        run = db.get(WorkflowRun, run_id)
        if run is not None:
            run.status = status
            run.outcome = outcome
            run.review_reason = final.get("review_reason")
            run.error_code = final.get("error_code")
            run.error_message = final.get("error")
            run.finished_at = utcnow()
            if run.company_id:
                company = db.get(Company, run.company_id)
                if company is not None:
                    company.workflow_status = {
                        "completed": "qualified" if final.get("decision") == "qualified" else "closed",
                        "needs_review": "needs_review",
                        "rejected": "rejected",
                        "failed": "failed_permanent",
                    }.get(status, company.workflow_status)

    return final
