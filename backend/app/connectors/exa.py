"""Exa.ai Search API connector for company discovery (fallback).

Docs: https://docs.exa.ai/
"""

from __future__ import annotations

import asyncio
import os
import urllib.parse
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


class ExaSearchConnector(BaseConnector):
    """Exa Search API connector for company discovery (fallback).

    Exa provides AI-powered search with good coverage for business/tech companies.
    """

    BASE_URL = "https://api.exa.ai/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 20.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key=api_key, timeout=timeout)
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_type(self) -> str:
        return "web_search"

    @property
    def provider(self) -> str:
        return "exa"

    @property
    def role(self) -> ConnectorRole:
        return ConnectorRole.DISCOVERY

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_query(self, query: DiscoveryQuery) -> str:
        """Build an Exa search query from campaign criteria."""
        parts = []

        # Sector/industry keywords
        if query.sectors:
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
        """Parse Exa API response into CandidateCompany records."""
        candidates = []

        results = data.get("results", [])
        for idx, result in enumerate(results[: query.max_results]):
            url = result.get("url", "")
            title = result.get("title", "")
            text = result.get("text", "")

            # Extract domain from URL
            domain = None
            if url:
                try:
                    parsed = urllib.parse.urlparse(url)
                    domain = parsed.netloc.lower()
                    if domain.startswith("www."):
                        domain = domain[4:]
                except Exception:
                    pass

            # Heuristic: use title as company name
            name = title.split(" - ")[0].split(" | ")[0].strip()
            if not name:
                name = title[:100]

            candidate = CandidateCompany(
                name=name,
                website_domain=domain,
                country=None,
                sector=None,
                employee_min=None,
                employee_max=None,
                source_url=url,
                snippet=text[:500] if text else None,
                provider_meta={
                    "exa_result_index": idx,
                    "exa_url": url,
                    "exa_title": title,
                    "exa_score": result.get("score"),
                },
            )
            candidates.append(candidate)

        return candidates

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """Discover candidate companies using Exa Search."""
        request_meta = {
            "query_text": self._build_query(query),
            "max_results": query.max_results,
            "fixture_mode": False,
        }

        if not is_configured(self):
            return self._make_result(
                status=ConnectorStatus.NOT_CONFIGURED,
                candidates=[],
                error_code="missing_api_key",
                error_message="EXA_API_KEY not configured",
                request_meta=request_meta,
            )

        search_query = self._build_query(query)
        payload = {
            "query": search_query,
            "type": "neural",  # neural search for better relevance
            "num_results": min(query.max_results, 10),
            "include_domains": [],
            "exclude_domains": [],
            "start_crawl_date": None,
            "end_crawl_date": None,
        }

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post(self.BASE_URL, json=payload)

                if response.status_code == 429:
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
                        error_message="Invalid or expired EXA_API_KEY",
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
        """Exa Search does not support enrichment."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="Exa Search connector does not support enrichment",
        )


# Singleton instance for app lifetime
_exa_connector: Optional[ExaSearchConnector] = None


def get_exa_connector() -> ExaSearchConnector:
    """Get or create the Exa Search connector singleton."""
    global _exa_connector
    if _exa_connector is None:
        api_key = os.getenv("EXA_API_KEY", "").strip()
        _exa_connector = ExaSearchConnector(
            api_key=api_key if api_key else None,
        )
    return _exa_connector