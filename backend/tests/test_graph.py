"""LangGraph workflow: transitions, routing, review, rejection and failure paths."""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.graph import qualify
from app.models import StageEvent, WorkflowRun

from .conftest import make_company_payload


def _run(client, campaign, company=None, **extra):
    payload = {"campaign_id": campaign["id"], "company": company or make_company_payload()}
    payload.update(extra)
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _events(run_id) -> list[StageEvent]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(StageEvent)
                .where(StageEvent.run_id == run_id)
                .order_by(StageEvent.id)
            ).all()
        )


# --- happy path ------------------------------------------------------------


def test_graph_walks_start_find_merge_evaluate_finish(client, campaign):
    run = _run(client, campaign)

    # With all enrichment connectors NOT_CONFIGURED (fixture mode),
    # the deterministic score is 60 -> needs_human_review
    assert run["outcome"] == "needs_human_review"
    assert run["status"] == "needs_review"
    # Updated workflow includes enrichment stages and scoring
    stages = [e["stage"] for e in run["events"]]
    assert stages[:5] == [
        "start",
        "find",
        "merge",
        "evaluate",
        "website_enrichment",
    ]
    assert "jobs_enrichment" in stages
    assert "news_enrichment" in stages
    assert "sec_enrichment" in stages
    assert "opencorporates_enrichment" in stages
    assert "scoring" in stages
    assert "finish" in stages
    assert all(e["status"] in ("ok", "held_for_review") for e in run["events"] if e["stage"] != "stop_after_error")


def test_qualified_decision_is_recorded(client, campaign):
    run = _run(client, campaign)

    evaluate_event = next(e for e in run["events"] if e["stage"] == "evaluate")
    assert evaluate_event["details"]["decision"] == "qualified"
    assert evaluate_event["details"]["checks"] == [
        {"rule": "country", "status": "pass", "detail": "Country 'United States' is in the campaign list."},
        {
            "rule": "sector",
            "status": "pass",
            "detail": "Sector 'software' matches a campaign keyword.",
        },
        {
            "rule": "employee_range",
            "status": "pass",
            "detail": "25-60 employees overlaps the campaign range 20-200.",
        },
        {"rule": "website_domain", "status": "pass", "detail": "A website domain is present."},
    ]
    
    # Check scoring stage exists and has results
    # In fixture mode (no enrichment API keys), score is 60 -> needs_review
    scoring_event = next(e for e in run["events"] if e["stage"] == "scoring")
    assert scoring_event["status"] == "held_for_review"
    assert "score_breakdown" in scoring_event["details"]
    assert scoring_event["details"]["score_breakdown"]["total_score"] == 60
    assert scoring_event["details"]["score_breakdown"]["qualification"] == "needs_review"


def test_find_node_records_that_discovery_is_not_configured(client, campaign):
    run = _run(client, campaign)
    find_event = next(e for e in run["events"] if e["stage"] == "find")
    assert find_event["details"]["discovery_connectors"] == []
    assert find_event["details"]["status"] == "not_configured"

    with SessionLocal() as db:
        from app.models import SourceRecord

        rows = db.scalars(
            select(SourceRecord).where(
                SourceRecord.company_id == run["company_id"],
                SourceRecord.source_type == "discovery",
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].status == "not_configured"


# --- needs human review ----------------------------------------------------


def test_missing_required_fact_routes_to_human_review(client, campaign):
    run = _run(
        client,
        campaign,
        make_company_payload(country=None, website_domain=None),
    )

    assert run["outcome"] == "needs_human_review"
    assert run["status"] == "needs_review"
    assert run["review_reason"]
    assert "country" in run["review_reason"]
    assert "website_domain" in run["review_reason"]

    stages = [e["stage"] for e in run["events"]]
    assert "hold_for_review" in stages
    assert "finish" not in stages
    assert "reject" not in stages

    held = next(e for e in run["events"] if e["stage"] == "hold_for_review")
    assert held["status"] == "held_for_review"


def test_unknown_fact_is_never_treated_as_a_match(client, campaign):
    run = _run(client, campaign, make_company_payload(country=""))

    assert run["outcome"] == "needs_human_review"
    evaluate_event = next(e for e in run["events"] if e["stage"] == "evaluate")
    country_check = next(c for c in evaluate_event["details"]["checks"] if c["rule"] == "country")
    assert country_check["status"] == "unknown"


def test_duplicate_domain_routes_to_human_review(client, campaign):
    first = _run(client, campaign, make_company_payload(canonical_name="Dup One"))
    second = _run(client, campaign, make_company_payload(canonical_name="Dup Two"))

    assert second["outcome"] == "needs_human_review"
    assert "Duplicate candidate" in second["review_reason"]
    assert str(first["company_id"]) in second["review_reason"]

    stages = [e["stage"] for e in second["events"]]
    assert stages.index("merge") < stages.index("hold_for_review")
    assert "evaluate" not in stages


# --- rejection -------------------------------------------------------------


def test_clear_failure_is_rejected_not_reviewed(client, campaign):
    run = _run(client, campaign, make_company_payload(country="Canada"))

    assert run["outcome"] == "rejected"
    assert run["status"] == "rejected"
    assert run["review_reason"] is None

    stages = [e["stage"] for e in run["events"]]
    assert "reject" in stages
    assert "finish" not in stages
    assert "hold_for_review" not in stages


def test_employee_range_outside_campaign_is_rejected(client, campaign):
    run = _run(
        client,
        campaign,
        make_company_payload(employee_min=900, employee_max=1200),
    )
    assert run["outcome"] == "rejected"


# --- failure path ----------------------------------------------------------


def test_forced_failure_stops_the_run_and_does_not_advance(client, campaign):
    run = _run(client, campaign, fail_at="find")

    assert run["outcome"] == "stopped_after_error"
    assert run["status"] == "failed"
    assert run["error_code"] == "forced_test_failure"
    assert "fail_at=find" in run["error_message"]

    stages = [e["stage"] for e in run["events"]]
    assert stages == ["start", "find", "stop_after_error"]
    assert "evaluate" not in stages

    failed_event = next(e for e in run["events"] if e["stage"] == "find")
    assert failed_event["status"] == "failed"
    assert failed_event["error_code"] == "forced_test_failure"

    stop_event = next(e for e in run["events"] if e["stage"] == "stop_after_error")
    assert stop_event["details"]["record_advanced"] is False

    with SessionLocal() as db:
        from app.models import Company

        company = db.get(Company, run["company_id"])
        assert company.workflow_status == "failed_permanent"


def test_failure_in_evaluate_stops_before_the_terminal_nodes(client, campaign):
    run = _run(client, campaign, fail_at="evaluate")

    assert run["outcome"] == "stopped_after_error"
    assert run["status"] == "failed"
    assert [e["stage"] for e in run["events"]] == [
        "start",
        "find",
        "merge",
        "evaluate",
        "stop_after_error",
    ]


def test_retry_after_failure_completes(client, campaign):
    failed = _run(client, campaign, fail_at="merge")
    assert failed["status"] == "failed"

    retried = client.post(f"/api/runs/{failed['id']}/retry").json()
    # With all enrichment connectors NOT_CONFIGURED, outcome is needs_human_review (score 60)
    assert retried["status"] == "needs_review"
    assert retried["outcome"] == "needs_human_review"
    assert retried["company_id"] == failed["company_id"]


# --- qualification unit tests ---------------------------------------------


SETTINGS = {
    "countries": ["united states"],
    "sectors": ["software"],
    "employee_min": 20,
    "employee_max": 200,
    "require_domain": True,
}


def _statuses(checks):
    return {c["rule"]: c["status"] for c in checks}


def test_qualify_returns_pass_when_everything_matches():
    checks = qualify(
        {
            "country": "United States",
            "sector": "Software Development",
            "employee_min": 30,
            "employee_max": 80,
            "website_domain": "example.com",
        },
        SETTINGS,
    )
    assert set(_statuses(checks).values()) == {"pass"}


def test_qualify_never_marks_missing_data_as_pass():
    checks = qualify(
        {"country": None, "sector": None, "employee_min": None, "employee_max": None,
         "website_domain": None},
        SETTINGS,
    )
    assert "pass" not in _statuses(checks).values()
    assert set(_statuses(checks).values()) == {"unknown"}


def test_qualify_reports_conflicting_range_shape_as_unknown():
    checks = qualify(
        {
            "country": "United States",
            "sector": "software",
            "employee_min": 30,
            "employee_max": None,
            "website_domain": "example.com",
        },
        SETTINGS,
    )
    assert _statuses(checks)["employee_range"] == "unknown"


def test_qualify_skips_rules_the_campaign_does_not_configure():
    checks = qualify({"country": "France", "sector": "anything"}, {"require_domain": False})
    assert checks == []


def test_qualify_fails_on_wrong_country():
    checks = qualify(
        {
            "country": "France",
            "sector": "software",
            "employee_min": 30,
            "employee_max": 60,
            "website_domain": "example.com",
        },
        SETTINGS,
    )
    assert _statuses(checks)["country"] == "fail"
