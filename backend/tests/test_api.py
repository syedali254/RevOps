"""HTTP API: health, overview, workflow inspection and error handling."""

from __future__ import annotations

from .conftest import make_company_payload


def test_health_reports_dry_run_and_connector_state(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["safety"]["dry_run"] is True
    assert body["safety"]["messages_sent"] == 0
    assert body["safety"]["banner"] == "DRY RUN — NO MESSAGES SENT"
    assert body["ai"]["status"] == "not_configured"
    assert set(body["connectors"]) == {
        "web_search",
        "company_website",
        "job_postings",
        "news_funding",
        "open_datasets",
    }
    assert all(status == "not_configured" for status in body["connectors"].values())


def test_safety_endpoint_is_always_blocking(client):
    blocked = client.get("/api/safety/evaluate", params={"channel": "email", "approved": "true"})
    assert blocked.status_code == 200
    assert blocked.json()["result"] == "BLOCKED"
    assert blocked.json()["dry_run"] is True

    unapproved = client.get("/api/safety/evaluate", params={"channel": "email"})
    assert unapproved.json()["result"] == "BLOCKED"
    assert "approval" in unapproved.json()["reason"].lower()


def test_safety_evaluate_rejects_unknown_channel(client):
    assert (
        client.get("/api/safety/evaluate", params={"channel": "fax"}).status_code == 422
    )


def test_sources_are_listed_as_not_configured(client):
    sources = client.get("/api/sources").json()
    assert len(sources) == 5
    assert {s["role"] for s in sources} == {"discovery", "enrichment", "both"}
    assert all(s["status"] == "not_configured" for s in sources)


def test_overview_starts_empty(client):
    body = client.get("/api/overview").json()
    assert body["counts"]["campaigns"] == 0
    assert body["counts"]["companies"] == 0
    assert body["counts"]["runs"] == 0
    assert body["recent_runs"] == []
    assert body["next_actions"]
    assert body["safety"]["dry_run"] is True


def test_overview_reflects_real_database_state(client, campaign):
    client.post(
        "/api/runs",
        json={
            "campaign_id": campaign["id"],
            "company": make_company_payload(canonical_name="Overview Co"),
        },
    )
    client.post(
        "/api/runs",
        json={
            "campaign_id": campaign["id"],
            "company": {"canonical_name": "Review Co"},
        },
    )

    body = client.get("/api/overview").json()
    assert body["counts"]["campaigns"] == 1
    assert body["counts"]["companies"] == 2
    assert body["counts"]["test_companies"] == 2
    assert body["counts"]["retrieved_companies"] == 0
    assert body["counts"]["runs"] == 2
    # With all enrichment connectors NOT_CONFIGURED (fixture mode), both qualification runs are needs_review
    assert body["counts"]["runs_by_status"] == {"needs_review": 2}
    assert len(body["recent_runs"]) == 2
    assert any("human review" in a for a in body["next_actions"])


def test_run_detail_includes_readable_event_history(client, campaign):
    run = client.post(
        "/api/runs",
        json={"campaign_id": campaign["id"], "company": make_company_payload()},
    ).json()

    detail = client.get(f"/api/runs/{run['id']}").json()
    assert detail["campaign_name"] == campaign["name"]
    assert detail["company_name"] == "Acme Analytics Co"
    assert detail["is_test_run"] is True
    # With all enrichment connectors NOT_CONFIGURED (fixture mode), score is 60 -> needs_review
    assert detail["status"] == "needs_review"
    assert len(detail["events"]) >= 9  # start, find, merge, evaluate, 5 enrichment stages, scoring, finish
    for event in detail["events"]:
        assert event["started_at"] and event["finished_at"]
        assert isinstance(event["details"], dict)


def test_run_not_found_returns_404(client):
    assert client.get("/api/runs/424242").status_code == 404
    assert client.post("/api/runs/424242/retry").status_code == 404


def test_run_for_unknown_campaign_returns_404(client):
    response = client.post("/api/runs", json={"campaign_id": 999, "company": {"canonical_name": "X"}})
    assert response.status_code == 404


def test_run_requires_company_or_company_id(client, campaign):
    response = client.post("/api/runs", json={"campaign_id": campaign["id"]})
    assert response.status_code == 422


def test_manual_event_is_labelled_as_manual(client, campaign):
    run = client.post(
        "/api/runs",
        json={"campaign_id": campaign["id"], "company": {"canonical_name": "Note Co"}},
    ).json()

    created = client.post(
        f"/api/runs/{run['id']}/events",
        json={"stage": "manual_note", "status": "ok", "message": "Reviewer accepted the record"},
    )
    assert created.status_code == 201
    assert created.json()["details"]["manual"] is True

    detail = client.get(f"/api/runs/{run['id']}").json()
    assert detail["events"][-1]["stage"] == "manual_note"


def test_cors_allows_the_vite_dev_origin(client):
    response = client.get(
        "/api/health",
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_cors_rejects_unknown_origin(client):
    response = client.get(
        "/api/health",
        headers={"Origin": "http://evil.example.com"},
    )
    assert response.headers.get("access-control-allow-origin") is None
