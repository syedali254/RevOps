"""Database behaviour: persistence, settings snapshots and evidence rows."""

from __future__ import annotations

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Campaign, Company, SourceRecord, StageEvent, WorkflowRun

from .conftest import make_company_payload


def test_campaign_is_persisted_and_retrievable(client, campaign):
    assert campaign["id"] > 0

    listed = client.get("/api/campaigns").json()
    assert len(listed) == 1
    assert listed[0]["name"] == "US B2B software — M1 test campaign"

    fetched = client.get(f"/api/campaigns/{campaign['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["settings"]["employee_min"] == 20
    assert fetched.json()["settings"]["employee_max"] == 200


def test_campaign_settings_are_stored_as_a_snapshot(client, campaign):
    """Settings are stored per campaign, not globally."""
    second = client.post(
        "/api/campaigns",
        json={"name": "Second campaign", "settings": {"countries": ["Canada"],
                                                       "sectors": ["fintech"],
                                                       "employee_min": 2,
                                                       "employee_max": 10,
                                                       "target_titles": [],
                                                       "exclusions": [],
                                                       "require_domain": False}},
    ).json()

    assert second["settings"]["countries"] == ["Canada"]
    assert client.get(f"/api/campaigns/{campaign['id']}").json()["settings"]["countries"] == [
        "United States"
    ]


def test_campaign_name_cannot_be_blank(client):
    response = client.post("/api/campaigns", json={"name": "   "})
    assert response.status_code == 422


def test_missing_campaign_returns_404(client):
    assert client.get("/api/campaigns/9999").status_code == 404


def test_company_domain_is_normalized_on_create(client, campaign):
    run = client.post(
        "/api/runs",
        json={
            "campaign_id": campaign["id"],
            "company": {
                "canonical_name": "Acme Analytics Co",
                "website_domain": "HTTPS://Acme-Analytics.example.com/pricing?x=1",
            },
        },
    )
    assert run.status_code == 201, run.text
    company_id = run.json()["company_id"]

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        assert company is not None
        assert company.website_domain == "acme-analytics.example.com"
        assert company.normalized_name == "acme analytics co"
        assert company.record_kind == "test_seed"


def test_manual_seed_creates_a_source_record(client, campaign):
    run = client.post(
        "/api/runs",
        json={"campaign_id": campaign["id"], "company": {"canonical_name": "Seeded Co"}},
    ).json()

    with SessionLocal() as db:
        rows = db.scalars(
            select(SourceRecord).where(
                SourceRecord.company_id == run["company_id"],
                SourceRecord.source_type == "manual_test_seed",
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].provider == "user_input"
        assert rows[0].status == "success_with_results"
        assert rows[0].retrieved_at is not None


def test_stage_events_are_persisted_with_timestamps(client, campaign):
    run = client.post(
        "/api/runs",
        json={"campaign_id": campaign["id"], "company": make_company_payload()},
    ).json()

    with SessionLocal() as db:
        events = db.scalars(
            select(StageEvent).where(StageEvent.run_id == run["id"]).order_by(StageEvent.id)
        ).all()
        # Updated workflow includes enrichment stages and scoring
        stages = [e.stage for e in events]
        assert stages[:5] == ["start", "find", "merge", "evaluate", "website_enrichment"]
        assert "jobs_enrichment" in stages
        assert "news_enrichment" in stages
        assert "sec_enrichment" in stages
        assert "opencorporates_enrichment" in stages
        assert "scoring" in stages
        assert "finish" in stages
        for event in events:
            assert event.started_at is not None
            assert event.finished_at is not None
            # Some stages may be held_for_review (scoring)
            assert event.status in ("ok", "held_for_review")


def test_workflow_run_is_persisted_with_outcome(client, campaign):
    run = client.post(
        "/api/runs",
        json={"campaign_id": campaign["id"], "company": make_company_payload()},
    ).json()

    with SessionLocal() as db:
        stored = db.get(WorkflowRun, run["id"])
        assert stored is not None
        # With all enrichment connectors NOT_CONFIGURED (fixture mode), score is 60 -> needs_review
        assert stored.status == "needs_review"
        assert stored.outcome == "needs_human_review"
        assert stored.finished_at is not None
        assert stored.started_at is not None


def test_retried_run_does_not_duplicate_the_company(client, campaign):
    run = client.post(
        "/api/runs",
        json={"campaign_id": campaign["id"], "company": {"canonical_name": "Retry Co"}},
    ).json()

    retried = client.post(f"/api/runs/{run['id']}/retry")
    assert retried.status_code == 201
    assert retried.json()["company_id"] == run["company_id"]
    assert retried.json()["id"] != run["id"]

    companies = client.get("/api/companies", params={"campaign_id": campaign["id"]}).json()
    assert len(companies) == 1
    assert len(client.get("/api/runs").json()) == 2
