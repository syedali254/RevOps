"""Tests for the Brave Search connector and connector base."""

from __future__ import annotations

import asyncio
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

from app.connectors.base import (
    BaseConnector,
    CandidateCompany,
    ConnectorResult,
    ConnectorRole,
    ConnectorStatus,
    DiscoveryQuery,
    EnrichmentQuery,
    get_connector_status,
    is_configured,
)
from app.connectors.brave_search import BraveSearchConnector, FIXTURE_CANDIDATES


class DummyConnector(BaseConnector):
    """Test connector that returns controlled results."""

    def __init__(self, should_fail: bool = False, fail_code: str = "test_error"):
        super().__init__(api_key="test-key")
        self.should_fail = should_fail
        self.fail_code = fail_code

    @property
    def source_type(self) -> str:
        return "test_source"

    @property
    def provider(self) -> str:
        return "test_provider"

    @property
    def role(self) -> ConnectorRole:
        return ConnectorRole.DISCOVERY

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        if self.should_fail:
            return ConnectorResult(
                source_type=self.source_type,
                provider=self.provider,
                role=self.role,
                status=ConnectorStatus.FAILED,
                candidates=[],
                error_code=self.fail_code,
                error_message="Simulated failure",
            )
        return ConnectorResult(
            source_type=self.source_type,
            provider=self.provider,
            role=self.role,
            status=ConnectorStatus.SUCCESS_WITH_RESULTS,
            candidates=[
                CandidateCompany(
                    name="Test Company",
                    website_domain="test.example.com",
                    country="United States",
                    sector="software",
                    source_url="https://test.example.com",
                    snippet="A test company.",
                )
            ],
        )

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        return ConnectorResult(
            source_type=self.source_type,
            provider=self.provider,
            role=self.role,
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported",
            error_message="Enrichment not supported",
        )


def test_connector_status_not_configured():
    connector = BraveSearchConnector(api_key="")
    assert is_configured(connector) is False
    assert get_connector_status(connector) == ConnectorStatus.NOT_CONFIGURED


def test_connector_status_configured():
    connector = BraveSearchConnector(api_key="test-key")
    assert is_configured(connector) is True
    assert get_connector_status(connector) == ConnectorStatus.SUCCESS_EMPTY


def test_candidate_company_normalized_domain():
    c = CandidateCompany(name="Test", website_domain="HTTPS://Test.Example.Com/Path?x=1")
    assert c.normalized_domain() == "test.example.com"

    c2 = CandidateCompany(name="Test", website_domain="test.example.com")
    assert c2.normalized_domain() == "test.example.com"

    c3 = CandidateCompany(name="Test", website_domain=None)
    assert c3.normalized_domain() is None


def test_dummy_connector_success():
    connector = DummyConnector()
    query = DiscoveryQuery(campaign_id=1, countries=["United States"], sectors=["software"])
    result = asyncio.run(connector.discover(query))

    assert result.status == ConnectorStatus.SUCCESS_WITH_RESULTS
    assert len(result.candidates) == 1
    assert result.candidates[0].name == "Test Company"
    assert result.source_type == "test_source"
    assert result.provider == "test_provider"


def test_dummy_connector_failure():
    connector = DummyConnector(should_fail=True, fail_code="rate_limited")
    query = DiscoveryQuery(campaign_id=1)
    result = asyncio.run(connector.discover(query))

    assert result.status == ConnectorStatus.FAILED
    assert result.error_code == "rate_limited"
    assert len(result.candidates) == 0


def test_brave_fixture_mode():
    """Brave connector in fixture mode returns controlled candidates."""
    connector = BraveSearchConnector(api_key=None, use_fixture=True)
    query = DiscoveryQuery(campaign_id=1, max_results=3)

    result = asyncio.run(connector.discover(query))

    assert result.status == ConnectorStatus.SUCCESS_WITH_RESULTS
    assert len(result.candidates) == 3
    assert result.request_meta.get("fixture_mode") is True
    # Check candidate structure
    first = result.candidates[0]
    assert first.name == "Acme Analytics Co"
    assert first.website_domain == "acme-analytics.example.com"
    assert first.source_url is not None


def test_brave_fixture_respects_max_results():
    connector = BraveSearchConnector(api_key=None, use_fixture=True)
    query = DiscoveryQuery(campaign_id=1, max_results=2)
    result = asyncio.run(connector.discover(query))
    assert len(result.candidates) == 2


def test_connector_result_is_success():
    result = ConnectorResult(
        source_type="test",
        provider="test",
        role=ConnectorRole.DISCOVERY,
        status=ConnectorStatus.SUCCESS_WITH_RESULTS,
    )
    assert result.is_success() is True

    result2 = ConnectorResult(
        source_type="test",
        provider="test",
        role=ConnectorRole.DISCOVERY,
        status=ConnectorStatus.SUCCESS_EMPTY,
    )
    assert result2.is_success() is True

    result3 = ConnectorResult(
        source_type="test",
        provider="test",
        role=ConnectorRole.DISCOVERY,
        status=ConnectorStatus.FAILED,
    )
    assert result3.is_success() is False