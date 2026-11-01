"""Tests for the Hacker News Who-is-Hiring discovery connector.

All tests are fixture-based: no live API calls, no network. The connector's
HTTP layer is stubbed out and the parsing/matching logic runs against samples
copied from the real "Ask HN: Who is hiring?" thread format.
"""

from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from app.connectors.base import ConnectorStatus, DiscoveryQuery
from app.connectors.hn_hiring import HNHiringConnector, get_hn_connector


def run(coro):
    """Run a coroutine to completion on a fresh loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def make_query(**overrides) -> DiscoveryQuery:
    base = dict(
        campaign_id=1,
        countries=["United States"],
        sectors=["software", "saas"],
        employee_min=20,
        employee_max=200,
        max_results=50,
    )
    base.update(overrides)
    return DiscoveryQuery(**base)


# Realistic samples in the exact format used by the monthly HN thread.
STORY = {"objectID": "43000000", "title": "Ask HN: Who is hiring? (October 2026)"}

THREAD = {
    "objectID": "43000000",
    "title": "Ask HN: Who is hiring? (October 2026)",
    "children": [
        {
            "objectID": "43000001",
            "created_at": "2026-10-01T10:00:00Z",
            "text": 'Acme Analytics | <a href="https://acme-analytics.example" rel="nofollow">https://acme-analytics.example</a> | San Francisco, CA | Senior Backend Engineer (Python, GCP) | Full time',
        },
        {
            "objectID": "43000002",
            "created_at": "2026-10-01T10:00:05Z",
            "text": 'Globex Cyber | London / Remote | Security Engineer | Full time — apply at <a href="https://globex.example.com/careers">careers</a>',
        },
        {
            "objectID": "43000003",
            "created_at": "2026-10-01T10:00:10Z",
            "text": 'RemoteOnly Labs | 100% Remote (worldwide) | Data Platform Engineer | see <a href="https://remote-labs.example">site</a>',
        },
        {
            "objectID": "43000004",
            "created_at": "2026-10-01T10:00:15Z",
            "text": "I'm a recruiter, not a company — sorry!",
        },
        {
            "objectID": "43000005",
            "created_at": "2026-10-01T10:00:20Z",
            "text": "X (just two words, no pipes) but no location structure",
        },
        {
            "objectID": "43000006",
            "created_at": "2026-10-01T10:00:25Z",
            "text": '<a href="https://news.ycombinator.com/submitted?id=hn-user">HNSelfPromo</a> | Berlin, Germany | Not relevant to our sectors',
        },
        {
            "objectID": "43000007",
            "created_at": "2026-10-01T10:00:35Z",
            "text": "Sidekick Labs | Senior Engineer | REMOTE (US) | apply at linkedin.com/sidekick/labs",
        },
        {
            "objectID": "43000008",
            "created_at": "2026-10-01T10:00:40Z",
            "text": (
                'Escapely | Engineers | REMOTE | <a href="https:&#x2F;&#x2F;www.linkedin.com&#x2F;in&#x2F;founder" '
                'rel="nofollow">contact</a> <a href="https:&#x2F;&#x2F;escapely.example" rel="nofollow">site</a>'
            ),
        },
        # Duplicate id — must be skipped
        {"objectID": "43000001", "created_at": "2026-10-01T10:00:30Z", "text": "Acme Analytics | Duplicate | Ignore"},
    ],
}


def stub_fetch(connector: HNHiringConnector, story: dict[str, Any], thread: dict[str, Any]):
    """Replace the HTTP layer with canned responses."""
    connector._find_latest_hiring_thread = _no_op_finder(story)  # type: ignore[method-assign]

    async def fake_get_json(path, params=None):
        if path.startswith("/items/"):
            return thread
        raise AssertionError(f"unexpected path {path}")

    connector._get_json = fake_get_json  # type: ignore[method-assign]


def _no_op_finder(story):
    async def finder():
        return story

    return finder


# --- parsing tests -----------------------------------------------------------


def test_parse_post_extracts_company_location_role_domain():
    connector = HNHiringConnector()
    post = connector._parse_post(THREAD["children"][0])
    assert post is not None
    assert post.company == "Acme Analytics"
    assert post.role == "Senior Backend Engineer (Python, GCP)"
    assert post.domain == "acme-analytics.example"
    assert post.permalink.endswith("id=43000001")
    # San Francisco sits inside the United States alias list
    assert connector._match_country(post.location, ["United States"]) == "United States"


def test_parse_post_rejects_non_company_comments():
    connector = HNHiringConnector()
    # Recruiter intro (no pipes)
    assert connector._parse_post(THREAD["children"][3]) is None
    # Two words without location structure
    assert connector._parse_post(THREAD["children"][4]) is None


def test_parse_post_ignores_hn_internal_links_as_domain():
    connector = HNHiringConnector()
    post = connector._parse_post(THREAD["children"][5])
    assert post is not None
    # The only link points at ycombinator.com — that is NOT a company domain
    assert post.domain is None


def test_parse_post_blocklists_bare_social_url_segment():
    """A bare "linkedin.com/..." segment must never become the company domain."""
    connector = HNHiringConnector()
    post = connector._parse_post(THREAD["children"][6])
    assert post is not None
    assert post.company == "Sidekick Labs"
    # linkedin.com is a jobs page, not the company site → domain must be None
    assert post.domain is None


def test_parse_post_unescapes_hn_hrefs_and_skips_social_links():
    """HN HTML-escapes hrefs (`&#x2F;`); the real company link after a social
    one must still be found."""
    connector = HNHiringConnector()
    post = connector._parse_post(THREAD["children"][7])
    assert post is not None
    assert post.company == "Escapely"
    assert post.domain == "escapely.example"


def test_match_country_aliases():
    connector = HNHiringConnector()
    assert connector._match_country("NYC, USA", ["United States"]) == "United States"
    assert connector._match_country("London, UK", ["United Kingdom"]) == "United Kingdom"
    assert connector._match_country("Berlin, Germany", ["United States"]) is None
    assert connector._match_country("", ["United States"]) is None


# --- discovery behaviour ------------------------------------------------------


def test_discover_returns_parsed_candidates_and_skips_duplicates(client):
    connector = HNHiringConnector()
    stub_fetch(connector, STORY, THREAD)

    result = run(connector.discover(make_query()))
    assert result.status == ConnectorStatus.SUCCESS_WITH_RESULTS
    assert result.provider == "hn"

    names = [c.name for c in result.candidates]
    assert result.status == ConnectorStatus.SUCCESS_WITH_RESULTS
    # Acme kept (San Francisco → United States), Globex kept (has "Remote")
    assert "Acme Analytics" in names
    acme = next(c for c in result.candidates if c.name == "Acme Analytics")
    assert acme.country == "United States"
    # London/Remote company: kept (remote is acceptable), but country stays
    # honestly None — the engine never guesses.
    globex = next(c for c in result.candidates if c.name == "Globex Cyber")
    assert globex.country is None
    # Duplicate post (same objectID) is skipped — no second Acme entry
    assert names.count("Acme Analytics") == 1
    # Recruiter junk never becomes a candidate
    assert all(name != "I'm a recruiter, not a company" for name in names)
    # Every candidate carries HN permalink provenance
    for candidate in result.candidates:
        assert candidate.source_url.startswith("https://news.ycombinator.com/item?id=4")

    meta = result.request_meta
    # HNSelfPromo is caught by the sector-relevance filter before the country gate
    assert meta["skipped_not_relevant"] >= 1
    # RemoteOnly stays in (remote is acceptable)
    assert "RemoteOnly Labs" in names


def test_location_gate_without_sector_filters(client):
    """With no sector filters, non-matching localities are gated out."""
    connector = HNHiringConnector()
    stub_fetch(connector, STORY, THREAD)
    result = run(connector.discover(make_query(countries=["United States"], sectors=[])))

    names = [c.name for c in result.candidates]
    # Berlin-only company: no remote token, outside United States → gated out
    assert "HNSelfPromo" not in names
    assert result.request_meta["skipped_outside_location"] >= 1
    # Remote companies remain
    assert "RemoteOnly Labs" in names


def test_discover_empty_thread_reports_success_empty(client):
    connector = HNHiringConnector()
    stub_fetch(connector, STORY, {"objectID": "1", "title": "x", "children": []})

    result = run(connector.discover(make_query()))
    assert result.status == ConnectorStatus.SUCCESS_EMPTY
    assert result.candidates == []


@pytest.fixture()
def patched(monkeypatch):
    """Fixture-quality no-op for the sleep used between retries."""
    from app.connectors import hn_hiring as module

    async def instant_sleep(seconds):
        return None

    monkeypatch.setattr(module, "_sleep", instant_sleep)


def test_no_result_fields_stay_honest(client):
    """Unknown facts must stay None — never a guess."""
    connector = HNHiringConnector()
    stub_fetch(connector, STORY, THREAD)
    post = connector._parse_post(THREAD["children"][2])
    assert post is not None
    result = run(
        connector.discover(
            make_query(countries=[], sectors=[])  # no filters → accept remote-only company
        )
    )
    assert result.is_success(), result.error_message
    # Remote-only company has no country claim → country must stay None
    remote = [c for c in result.candidates if c.name == "RemoteOnly Labs"]
    assert remote and remote[0].country is None


def test_singleton_reuses_same_instance():
    assert get_hn_connector() is get_hn_connector()
