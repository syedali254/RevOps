"""Tavily Search API connector for company discovery.

Docs: https://docs.tavily.com/
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


class TavilySearchConnector(BaseConnector):
    """Tavily Search API connector for company discovery.

    Tavily is designed for AI agents and provides clean, structured search results
    with good coverage for company/business searches.
    """

    BASE_URL = "https://api.tavily.com/search"

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
        return "tavily"

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
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_query(self, query: DiscoveryQuery) -> str:
        """Build a Tavily search query from campaign criteria."""
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
        """Parse Tavily API response into CandidateCompany records."""
        candidates = []

        results = data.get("results", [])
        for idx, result in enumerate(results[: query.max_results]):
            url = result.get("url", "")
            title = result.get("title", "")
            content = result.get("content", "")

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
                country=None,  # Tavily doesn't reliably return country
                sector=None,   # Would need enrichment
                employee_min=None,
                employee_max=None,
                source_url=url,
                snippet=content[:500] if content else None,
                provider_meta={
                    "tavily_result_index": idx,
                    "tavily_url": url,
                    "tavily_title": title,
                    "tavily_score": result.get("score"),
                },
            )
            candidates.append(candidate)

        return candidates

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """Discover candidate companies using Tavily Search."""
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
                error_message="TAVILY_API_KEY not configured",
                request_meta=request_meta,
            )

        search_query = self._build_query(query)
        payload = {
            "api_key": self.api_key,
            "query": search_query,
            "search_depth": "basic",
            "include_answer": False,
            "include_images": False,
            "include_raw_content": False,
            "max_results": min(query.max_results, 10),
            "include_domains": [],
            "exclude_domains": [],
        }

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.post(self.BASE_URL, json=payload)

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
                        error_message="Invalid or expired TAVILY_API_KEY",
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
        """Tavily Search does not support enrichment."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="Tavily Search connector does not support enrichment",
        )


# Singleton instance for app lifetime
_tavily_connector: Optional[TavilySearchConnector] = None


def get_tavily_connector() -> TavilySearchConnector:
    """Get or create the Tavily Search connector singleton."""
    global _tavily_connector
    if _tavily_connector is None:
        api_key = os.getenv("TAVILY_API_KEY", "").strip()
        _tavily_connector = TavilySearchConnector(
            api_key=api_key if api_key else None,
        )
    return _tavily_connector