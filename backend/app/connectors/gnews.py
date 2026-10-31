"""GNews API connector for news and funding enrichment.

Docs: https://docs.gnews.io/
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import quote

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


@dataclass
class NewsArticle:
    """A news article from GNews."""
    title: str
    description: Optional[str]
    url: str
    source: str
    published_at: Optional[str]
    image: Optional[str]


class GNewsConnector(BaseConnector):
    """GNews API connector for news and funding enrichment."""

    BASE_URL = "https://gnews.io/api/v4/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key=api_key, timeout=timeout)
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_type(self) -> str:
        return "news_funding"

    @property
    def provider(self) -> str:
        return "gnews"

    @property
    def role(self) -> ConnectorRole:
        return ConnectorRole.ENRICHMENT

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "B2BLeadEngine/1.0",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _build_query(self, query: EnrichmentQuery) -> str:
        """Build a GNews search query from company info."""
        parts = []

        # Use company names
        if query.names:
            # Use the first name, quote it for exact matching
            name = query.names[0]
            parts.append(f'"{name}"')

        # Add domain if available
        if query.domains:
            domain = query.domains[0]
            parts.append(f"site:{domain}")

        return " ".join(parts)

    def _parse_articles(self, data: dict[str, Any]) -> list[dict]:
        """Parse GNews API response into article records."""
        articles = []
        for article in data.get("articles", []):
            articles.append({
                "title": article.get("title"),
                "description": article.get("description"),
                "url": article.get("url"),
                "source": article.get("source", {}).get("name") if article.get("source") else None,
                "published_at": article.get("publishedAt"),
                "image": article.get("image"),
            })
        return articles

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Enrich companies by searching GNews for relevant articles."""
        from ..models import Company, SourceRecord
        from ..db import session_scope

        request_meta = {
            "company_ids": company_ids,
        }

        if not company_ids:
            return self._make_result(
                status=ConnectorStatus.SUCCESS_EMPTY,
                candidates=[],
                request_meta=request_meta,
            )

        if not is_configured(self):
            return self._make_result(
                status=ConnectorStatus.NOT_CONFIGURED,
                candidates=[],
                error_code="missing_api_key",
                error_message="GNEWS_API_KEY not configured",
                request_meta=request_meta,
            )

        enriched_count = 0
        failed_count = 0
        total_articles = 0

        with session_scope() as db:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()

            for company in companies:
                # Build search query
                search_query = self._build_query(EnrichmentQuery(
                    campaign_id=query.campaign_id,
                    company_ids=[company.id],
                    domains=[company.website_domain] if company.website_domain else [],
                    names=[company.canonical_name],
                ))

                articles = await self._search_news(search_query)

                if articles:
                    total_articles += len(articles)
                    enriched_count += 1

                    # Store each article as a source record
                    for article in articles:
                        db.add(SourceRecord(
                            company_id=company.id,
                            source_type="enrichment",
                            provider="gnews",
                            source_url=article["url"],
                            retrieved_at=datetime.now(timezone.utc),
                            published_at=datetime.fromisoformat(article["published_at"].replace("Z", "+00:00")) if article.get("published_at") else None,
                            status="success_with_results",
                            raw_payload_json=__import__("json").dumps({
                                "title": article["title"],
                                "description": article["description"],
                                "source": article["source"],
                                "image": article["image"],
                            }),
                        ))
                else:
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="gnews",
                        source_url=f"https://gnews.io/api/v4/search?q={quote(self._build_query(query))}",
                        retrieved_at=datetime.now(timezone.utc),
                        status="success_empty",
                        error_message="No recent news articles found",
                    ))

        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS if enriched_count > 0 else ConnectorStatus.SUCCESS_EMPTY,
            candidates=[],
            request_meta={"company_ids": company_ids, "total_articles": sum(1 for _ in range(0))},  # placeholder
        )

    async def _search_news(self, query: str) -> list[dict]:
        """Search GNews for articles."""
        params = {
            "q": query,
            "token": self.api_key,
            "lang": "en",
            "max": 10,
            "sortby": "publishedAt",
        }

        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
                response = await client.get(self.BASE_URL, params=params)
                await client.aclose()

                if response.status_code == 429:
                    await asyncio.sleep(2**attempt)
                    continue

                if response.status_code == 401:
                    return []  # Invalid API key

                if response.status_code >= 500:
                    await asyncio.sleep(2**attempt)
                    continue

                response.raise_for_status()
                data = response.json()
                return self._parse_articles(data)

            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                continue
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                continue
            except Exception:
                break

        return []

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """GNews doesn't do discovery."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="GNews connector does not support discovery",
        )


# Singleton
_gnews_connector: Optional[GNewsConnector] = None


def get_gnews_connector() -> GNewsConnector:
    """Get or create the GNews connector singleton."""
    global _gnews_connector
    if _gnews_connector is None:
        api_key = os.getenv("GNEWS_API_KEY", "").strip()
        _gnews_connector = GNewsConnector(
            api_key=api_key if api_key else None,
        )
    return _gnews_connector