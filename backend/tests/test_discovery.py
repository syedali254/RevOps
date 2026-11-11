"""Tests for discovery runs and the updated LangGraph workflow."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure backend is on path
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Set test env before importing app modules
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(tempfile.mkdtemp(prefix="b2b_lead_engine_tests_")) / "test.db").as_posix()
os.environ["DRY_RUN"] = "true"
os.environ["FRONTEND_ORIGIN"] = "http://127.0.0.1:5173"
# Force fixture mode for Brave Search
os.environ["BRAVE_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app.connectors.base import ConnectorStatus
from app.db import Base, engine, init_db
from app.main import app

init_db()


@pytest.fixture(autouse=True)
def clean_tables():
    """Start every test from empty tables."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def campaign(client) -> dict:
    """A campaign with explicit, testable target settings."""
    response = client.post(
        "/api/campaigns",
        json={
            "name": "US B2B software — Discovery test",
            "settings": {
                "countries": ["United States"],
                "sectors": ["software", "it services", "data"],
                "employee_min": 20,
                "employee_max": 200,
                "target_titles": ["Founder", "CEO"],
                "exclusions": [],
                "require_domain": True,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- shared stubs for deterministic live-source control ---------------------


def _stub_result(status, error_code=None, error_message=None, candidates=None):
    from app.connectors.base import ConnectorResult, ConnectorRole

    return ConnectorResult(
        source_type="stub",
        provider="stub",
        role=ConnectorRole.DISCOVERY,
        status=status,
        candidates=candidates or [],
        error_code=error_code,
        error_message=error_message,
    )


def _stub_candidate():
    from app.connectors.base import CandidateCompany

    return CandidateCompany(
        name="StubCo",
        website_domain="stubco.example",
        source_url="https://stubco.example",
        snippet="stub candidate",
    )


class _StubDiscoveryConnector:
    """Stand-in for a live connector, returning a canned result."""

    def __init__(self, result):
        self._result = result

    async def discover(self, query):
        return self._result

    async def close(self):
        return None

    @property
    def provider(self):
        return "stub"


def test_create_discovery_run_fixture_mode(client, campaign):
    """Create a discovery run in fixture mode (no API key)."""
    response = client.post(
        "/api/discovery",
        json={"campaign_id": campaign["id"], "max_results": 5},
    )
    assert response.status_code == 201, response.text
    run = response.json()

    assert run["campaign_id"] == campaign["id"]
    assert run["run_type"] == "discovery"
    assert run["status"] == "completed"
    assert run["outcome"] == "continue"
    assert run["companies_created"] == 5  # Fixture returns 5 candidates
    assert run["companies_discovered"] == 5
    assert run["duplicates_found"] == 0
    assert len(run["events"]) >= 2  # start + find (and finish)


def test_discovery_run_creates_companies_with_source_records(client, campaign):
    """Discovery run should create companies with source records."""
    response = client.post(
        "/api/discovery",
        json={"campaign_id": campaign["id"], "max_results": 3},
    )
    assert response.status_code == 201
    run = response.json()

    # Get the companies created
    companies_response = client.get(f"/api/companies?campaign_id={campaign['id']}&record_kind=retrieved")
    assert companies_response.status_code == 200
    companies = companies_response.json()
    assert len(companies) == 3

    # Each company should have source records
    for company in companies:
        sources_response = client.get(f"/api/companies/{company['id']}/sources")
        assert sources_response.status_code == 200
        sources = sources_response.json()
        assert len(sources) >= 1
        discovery_source = next((s for s in sources if s["source_type"] == "discovery"), None)
        assert discovery_source is not None
        # Provider can be any discovery connector (brave, remoteok, yc, hn, tavily, exa)
        assert discovery_source["provider"] in ("brave", "remoteok", "yc", "hn", "tavily", "exa")
        assert discovery_source["status"] == "success_with_results"
        assert discovery_source["source_url"] is not None
        assert discovery_source["retrieved_at"] is not None
        assert isinstance(discovery_source["raw_payload"], dict)


def test_discovery_run_duplicate_handling(client, campaign, monkeypatch):
    """Running discovery twice should not create duplicate companies."""
    # Stub the live sources (RemoteOK / HN hit real network otherwise, and the
    # live candidate mix can shift between the two calls — the guarantee under
    # test is about de-duplication, not live-data stability).
    import app.graph as graph

    live_ok = _stub_result(
        status=ConnectorStatus.SUCCESS_WITH_RESULTS,
        candidates=[_stub_candidate()],
    )
    monkeypatch.setattr(graph, "get_remoteok_connector", lambda: _StubDiscoveryConnector(live_ok))
    monkeypatch.setattr(graph, "get_hn_connector", lambda: _StubDiscoveryConnector(live_ok))

    # First run
    response1 = client.post("/api/discovery", json={"campaign_id": campaign["id"], "max_results": 5})
    assert response1.status_code == 201
    run1 = response1.json()

    # Second run with same criteria (fixture returns same candidates)
    response2 = client.post("/api/discovery", json={"campaign_id": campaign["id"], "max_results": 5})
    assert response2.status_code == 201
    run2 = response2.json()

    # Should have found duplicates
    assert run2["duplicates_found"] == 5
    assert run2["companies_created"] == 0

    # Total companies should still be 5
    companies_response = client.get(f"/api/companies?campaign_id={campaign['id']}&record_kind=retrieved")
    companies = companies_response.json()
    assert len(companies) == 5

    # Each duplicate company should have 2 source records (one from each run)
    for company in companies:
        sources_response = client.get(f"/api/companies/{company['id']}/sources")
        sources = sources_response.json()
        discovery_sources = [s for s in sources if s["source_type"] == "discovery"]
        assert len(discovery_sources) == 2


def test_discovery_run_with_fail_at_find(client, campaign):
    """Discovery run with forced failure at find stage."""
    response = client.post(
        "/api/discovery",
        json={"campaign_id": campaign["id"], "max_results": 5, "fail_at": "find"},
    )
    assert response.status_code == 201
    run = response.json()

    assert run["status"] == "failed"
    assert run["outcome"] == "stopped_after_error"
    assert run["error_code"] == "forced_test_failure"
    assert "fail_at=find" in run["error_message"]

    # No companies should be created
    companies_response = client.get(f"/api/companies?campaign_id={campaign['id']}&record_kind=retrieved")
    companies = companies_response.json()
    assert len(companies) == 0


# --- resilient discovery: one source down must not kill the run -------------


def test_single_source_failure_does_not_stop_discovery(client, campaign, monkeypatch):
    """RemoteOK (or any single source) failing must not kill a run when other
    live sources succeeded — the failure is recorded, the run continues."""
    import app.graph as graph

    failed_result = _stub_result(
        status=ConnectorStatus.FAILED,
        error_code="fetch_failed",
        error_message="simulated network failure",
    )

    monkeypatch.setattr(
        graph, "get_remoteok_connector", lambda: _StubDiscoveryConnector(failed_result)
    )
    monkeypatch.setattr(
        graph,
        "get_hn_connector",
        lambda: _StubDiscoveryConnector(
            _stub_result(
                status=ConnectorStatus.SUCCESS_WITH_RESULTS,
                candidates=[_stub_candidate()],
            )
        ),
    )

    response = client.post(
        "/api/discovery",
        json={"campaign_id": campaign["id"], "max_results": 5},
    )
    assert response.status_code == 201
    run = response.json()

    assert run["outcome"] == "continue"
    assert run["status"] == "completed"

    find_event = next(e for e in run["events"] if e["stage"] == "find")
    details = find_event["details"]
    assert details["connector_statuses"]["remoteok"] == "failed"
    assert "remoteok" in details["degraded_sources"]
    assert any("remoteok" in note for note in details["degraded_notes"])
    # Companies were still created from the sources that worked
    assert details["created_companies"]


def test_all_live_sources_failing_still_stops_run(client, campaign, monkeypatch):
    """If NO live discovery source succeeded, the run must stop honestly."""
    import app.graph as graph

    failed_result = _stub_result(
        status=ConnectorStatus.FAILED,
        error_code="fetch_failed",
        error_message="simulated total outage",
    )
    monkeypatch.setattr(
        graph, "get_remoteok_connector", lambda: _StubDiscoveryConnector(failed_result)
    )
    monkeypatch.setattr(
        graph, "get_hn_connector", lambda: _StubDiscoveryConnector(failed_result)
    )

    response = client.post(
        "/api/discovery",
        json={"campaign_id": campaign["id"], "max_results": 5},
    )
    assert response.status_code == 201
    run = response.json()

    assert run["outcome"] == "stopped_after_error"
    assert run["status"] == "failed"
    assert run["error_code"] == "fetch_failed"


def test_list_discovery_runs(client, campaign):
    """List discovery runs endpoint."""
    client.post("/api/discovery", json={"campaign_id": campaign["id"], "max_results": 3})

    response = client.get(f"/api/discovery?campaign_id={campaign['id']}")
    assert response.status_code == 200
    runs = response.json()
    assert len(runs) == 1
    assert runs[0]["run_type"] == "discovery"


def test_get_discovery_run_detail(client, campaign):
    """Get discovery run detail."""
    create_response = client.post("/api/discovery", json={"campaign_id": campaign["id"], "max_results": 3})
    run_id = create_response.json()["id"]

    response = client.get(f"/api/discovery/{run_id}")
    assert response.status_code == 200
    run = response.json()
    assert run["id"] == run_id
    assert run["run_type"] == "discovery"
    assert run["companies_created"] == 3


def test_discovery_run_not_found(client):
    """Get non-existent discovery run returns 404."""
    response = client.get("/api/discovery/999999")
    assert response.status_code == 404


def test_qualification_run_still_works(client, campaign):
    """Qualification runs (single company) should still work after discovery changes."""
    # Create a company manually
    run_response = client.post(
        "/api/runs",
        json={
            "campaign_id": campaign["id"],
            "company": {
                "canonical_name": "Qualification Test Co",
                "website_domain": "qual-test.example.com",
                "country": "United States",
                "sector": "software",
                "employee_min": 30,
                "employee_max": 60,
            },
        },
    )
    assert run_response.status_code == 201
    run = run_response.json()

    assert run["run_type"] == "qualification"
    # With all enrichment connectors NOT_CONFIGURED (fixture mode), score is 60 -> needs_review
    assert run["status"] == "needs_review"
    assert run["outcome"] == "needs_human_review"
    assert run["company_id"] is not None
    assert run["company_name"] == "Qualification Test Co"


def test_list_runs_filters_by_type(client, campaign):
    """List runs should separate discovery and qualification runs."""
    client.post("/api/discovery", json={"campaign_id": campaign["id"], "max_results": 2})
    client.post(
        "/api/runs",
        json={
            "campaign_id": campaign["id"],
            "company": {"canonical_name": "Qual Co"},
        },
    )

    # All runs
    all_runs = client.get(f"/api/runs?campaign_id={campaign['id']}").json()
    assert len(all_runs) == 2

    # The /api/runs endpoint includes both types
    run_types = {r["run_type"] for r in all_runs}
    assert "discovery" in run_types
    assert "qualification" in run_types


def test_overview_includes_discovery_runs(client, campaign):
    """Overview should show discovery run counts."""
    client.post("/api/discovery", json={"campaign_id": campaign["id"], "max_results": 3})

    overview = client.get("/api/overview").json()
    assert overview["counts"]["runs"] >= 1
    # The overview counts all runs (discovery + qualification)
    # Check source health reflects configured connector
    web_search_status = next(s for s in overview["sources"] if s["key"] == "web_search")
    # In test fixture mode, the connector has no API key but runs in fixture mode
    # The overview checks for API key presence
    # Since we set BRAVE_API_KEY="" in test env, it shows as not_configured
    # but the run still works in fixture mode


def test_discovery_run_event_details(client, campaign):
    """Discovery run find stage should record detailed event info."""
    response = client.post("/api/discovery", json={"campaign_id": campaign["id"], "max_results": 2})
    run = response.json()

    find_event = next((e for e in run["events"] if e["stage"] == "find"), None)
    assert find_event is not None
    assert find_event["status"] == "ok"
    assert "created_companies" in find_event["details"]
    assert "candidates_returned" in find_event["details"]
    assert "query" in find_event["details"]
    assert find_event["details"]["candidates_returned"] == 2
    assert len(find_event["details"]["created_companies"]) == 2
    for company in find_event["details"]["created_companies"]:
        assert "id" in company
        assert "name" in company