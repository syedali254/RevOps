"""Brave Search API connector for company discovery.

Docs: https://api-dashboard.search.brave.com/documentation/pricing
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from .base import (
    BaseConnector,
    CandidateCompany,
    ConnectorResult,
    ConnectorRole,
    ConnectorStatus,
    DiscoveryQuery,
    EnrichmentQuery,
    is_configured,
)


# Fixture mode: when BRAVE_API_KEY is not set, return controlled test data
FIXTURE_CANDIDATES = [
    CandidateCompany(
        name="Acme Analytics Co",
        website_domain="acme-analytics.example.com",
        country="United States",
        sector="software",
        employee_min=35,
        employee_max=80,
        source_url="https://acme-analytics.example.com/about",
        snippet="Acme Analytics builds B2B data platforms for mid-market companies.",
        provider_meta={"brave_result_index": 0},
    ),
    CandidateCompany(
        name="Brightline Data Systems",
        website_domain="brightline-data.example.com",
        country="United States",
        sector="IT services",
        employee_min=50,
        employee_max=120,
        source_url="https://brightline-data.example.com",
        snippet="Brightline provides managed analytics and cloud migration services.",
        provider_meta={"brave_result_index": 1},
    ),
    CandidateCompany(
        name="CipherPoint Security",
        website_domain="cipherpoint.example.com",
        country="United States",
        sector="cybersecurity",
        employee_min=25,
        employee_max=60,
        source_url="https://cipherpoint.example.com/solutions",
        snippet="CipherPoint delivers zero-trust security for distributed teams.",
        provider_meta={"brave_result_index": 2},
    ),
    CandidateCompany(
        name="DataFlow Labs",
        website_domain="dataflow-labs.example.com",
        country="United States",
        sector="data",
        employee_min=15,
        employee_max=40,
        source_url="https://dataflow-labs.example.com",
        snippet="DataFlow Labs builds real-time streaming pipelines on Kafka and Flink.",
        provider_meta={"brave_result_index": 3},
    ),
    CandidateCompany(
        name="ElevateOps",
        website_domain="elevateops.example.com",
        country="United States",
        sector="software",
        employee_min=80,
        employee_max=150,
        source_url="https://elevateops.example.com/platform",
        snippet="ElevateOps automates incident response for SRE teams.",
        provider_meta={"brave_result_index": 4},
    ),
]


class BraveSearchConnector(BaseConnector):
    """Brave Search API discovery connector.

    Uses the Web Search endpoint to find candidate companies matching
    campaign criteria. Returns CandidateCompany records with source URLs
    and retrieval timestamps.
    """

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        use_fixture: bool = False,
    ):
        super().__init__(api_key=api_key, timeout=timeout)
        self.max_retries = max_retries
        self.use_fixture = use_fixture or not is_configured(self)
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_type(self) -> str:
        return "web_search"

    @property
    def provider(self) -> str:
        return "brave"

    @property
    def role(self) -> ConnectorRole:
        return ConnectorRole.DISCOVERY

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": self.api_key or "",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_query(self, query: DiscoveryQuery) -> str:
        """Build a Brave Search query from campaign criteria."""
        parts = []

        # Sector/industry keywords
        if query.sectors:
            # Use the first sector as primary, others as alternatives
            sector_terms = " OR ".join(f'"{s}"' for s in query.sectors[:3])
            parts.append(f"({sector_terms})")

        # Country
        if query.countries:
            country_terms = " OR ".join(f'"{c}"' for c in query.countries)
            parts.append(f"({country_terms})")

        # Company size hints
        if query.employee_min is not None or query.employee_max is not None:
            size_parts = []
            if query.employee_min is not None:
                size_parts.append(f"{query.employee_min}+ employees")
            if query.employee_max is not None:
                size_parts.append(f"up to {query.employee_max} employees")
            if size_parts:
                parts.append(" ".join(size_parts))

        # Add B2B technology context
        parts.append("B2B technology company")

        return " ".join(parts)

    def _parse_results(self, data: dict[str, Any], query: DiscoveryQuery) -> list[CandidateCompany]:
        """Parse Brave Search API response into CandidateCompany records."""
        candidates = []

        web_results = data.get("web", {}).get("results", [])
        for idx, result in enumerate(web_results[: query.max_results]):
            url = result.get("url", "")
            title = result.get("title", "")
            description = result.get("description", "")

            # Extract domain from URL
            domain = None
            if url:
                try:
                    parsed = urllib.parse.urlparse(url)
                    domain = parsed.netloc.lower()
                    # Remove www. prefix
                    if domain.startswith("www."):
                        domain = domain[4:]
                except Exception:
                    pass

            # Heuristic: use title as company name, description as snippet
            # In production, we'd do more sophisticated extraction
            name = title.split(" - ")[0].split(" | ")[0].strip()
            if not name:
                name = title[:100]

            candidate = CandidateCompany(
                name=name,
                website_domain=domain,
                country=None,  # Brave doesn't reliably return country
                sector=None,  # Would need enrichment
                employee_min=None,
                employee_max=None,
                source_url=url,
                snippet=description[:500] if description else None,
                provider_meta={
                    "brave_result_index": idx,
                    "brave_url": url,
                    "brave_title": title,
                },
            )
            candidates.append(candidate)

        return candidates

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """Discover candidate companies using Brave Search."""
        request_meta = {
            "query_text": self._build_query(query),
            "max_results": query.max_results,
            "fixture_mode": self.use_fixture,
        }

        # Fixture mode for testing without API key
        if self.use_fixture:
            return self._make_result(
                status=ConnectorStatus.SUCCESS_WITH_RESULTS,
                candidates=FIXTURE_CANDIDATES[: query.max_results],
                raw_response={"fixture": True, "count": len(FIXTURE_CANDIDATES)},
                request_meta=request_meta,
            )

        if not is_configured(self):
            return self._make_result(
                status=ConnectorStatus.NOT_CONFIGURED,
                candidates=[],
                error_code="missing_api_key",
                error_message="BRAVE_API_KEY not configured",
                request_meta=request_meta,
            )

        search_query = self._build_query(query)
        params = {
            "q": search_query,
            "count": min(query.max_results, 20),  # Brave max is 20 per request
            "search_lang": "en",
            "country": "us",
            "safesearch": "moderate",
        }

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.get(self.BASE_URL, params=params)

                if response.status_code == 429:
                    # Rate limited - retry with backoff
                    last_error = httpx.HTTPStatusError(
                        "Rate limited", request=response.request, response=response
                    )
                    await asyncio.sleep(2**attempt)
                    continue

                if response.status_code == 401:
                    return self._make_result(
                        status=ConnectorStatus.FAILED,
                        candidates=[],
                        error_code="auth_error",
                        error_message="Invalid or expired BRAVE_API_KEY",
                        request_meta=request_meta,
                    )

                if response.status_code >= 500:
                    last_error = httpx.HTTPStatusError(
                        f"Server error: {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    await asyncio.sleep(2**attempt)
                    continue

                response.raise_for_status()
                data = response.json()

                candidates = self._parse_results(data, query)

                return self._make_result(
                    status=(
                        ConnectorStatus.SUCCESS_WITH_RESULTS
                        if candidates
                        else ConnectorStatus.SUCCESS_EMPTY
                    ),
                    candidates=candidates,
                    raw_response=data,
                    request_meta=request_meta,
                )

            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                continue
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                continue
            except Exception as exc:
                last_error = exc
                break

        # All retries exhausted
        return self._make_result(
            status=ConnectorStatus.FAILED,
            candidates=[],
            error_code="request_failed",
            error_message=str(last_error) if last_error else "Unknown error",
            request_meta=request_meta,
        )

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Brave Search does not support enrichment (no company-specific enrichment)."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="Brave Search connector does not support enrichment",
        )


# Singleton instance for app lifetime
_brave_connector: Optional[BraveSearchConnector] = None


def get_brave_connector() -> BraveSearchConnector:
    """Get or create the Brave Search connector singleton."""
    global _brave_connector
    if _brave_connector is None:
        api_key = os.getenv("BRAVE_API_KEY", "").strip()
        _brave_connector = BraveSearchConnector(
            api_key=api_key if api_key else None,
            use_fixture=not bool(api_key),
        )
    return _brave_connector