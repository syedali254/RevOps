"""Greenhouse Job Board API connector for public job postings.

Docs: https://docs.greenhouse.io/job-board
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin

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


# Known public Greenhouse boards for testing
# These are real public boards that can be used for testing
KNOWN_GREENHOUSE_BOARDS = {
    "stripe": "stripe",
    "airbnb": "airbnb",
    "coinbase": "coinbase",
    "datadog": "datadoghq",
    "github": "github",
    "gitlab": "gitlab",
    "hubspot": "hubspot",
    "segment": "segment",
    "twilio": "twilio",
    "zendesk": "zendesk",
}


@dataclass
class JobPosting:
    """A job posting from Greenhouse."""
    id: int
    title: str
    location: Optional[str]
    department: Optional[str]
    absolute_url: str
    updated_at: Optional[str]
    content: Optional[str]


class GreenhouseConnector(BaseConnector):
    """Greenhouse Job Board API connector for enrichment.

    Uses the public Job Board API which requires no authentication.
    Board token must be known/verified for each company.
    """

    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

    def __init__(
        self,
        timeout: float = 15.0,
        max_retries: int = 2,
    ):
        super().__init__(api_key=None, timeout=timeout)
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_type(self) -> str:
        return "job_postings"

    @property
    def provider(self) -> str:
        return "greenhouse"

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

    def _parse_jobs(self, data: dict[str, Any]) -> list[dict]:
        """Parse Greenhouse API response into job records."""
        jobs = []
        for job in data.get("jobs", []):
            jobs.append({
                "id": job.get("id"),
                "title": job.get("title"),
                "location": job.get("location", {}).get("name") if job.get("location") else None,
                "department": job.get("departments", [{}])[0].get("name") if job.get("departments") else None,
                "absolute_url": job.get("absolute_url"),
                "updated_at": job.get("updated_at"),
                "content": job.get("content"),
            })
        return jobs

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Enrich companies by fetching their Greenhouse job boards.

        Requires known board tokens for each company. We don't guess tokens.
        """
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

        enriched_count = 0
        failed_count = 0
        total_jobs = 0

        with session_scope() as db:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()

            for company in companies:
                # We need a known board token - we don't guess
                # In production, this would come from a verified source
                # For now, check if we have a known test board for this company
                board_token = self._get_known_board_token(company)

                if not board_token:
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="greenhouse",
                        source_url=None,
                        retrieved_at=datetime.now(timezone.utc),
                        status="unsupported",
                        error_message="No verified Greenhouse board token for this company",
                    ))
                    continue

                jobs = await self._fetch_jobs(board_token)

                if jobs:
                    total_jobs += len(jobs)
                    enriched_count += 1

                    # Store each job as a source record
                    for job in jobs:
                        from ..models import SourceRecord
                        db.add(SourceRecord(
                            company_id=company.id,
                            source_type="enrichment",
                            provider="greenhouse",
                            source_url=job["absolute_url"],
                            retrieved_at=datetime.now(timezone.utc),
                            published_at=datetime.fromisoformat(job["updated_at"].replace("Z", "+00:00")) if job.get("updated_at") else None,
                            status="success_with_results",
                            raw_payload_json=__import__("json").dumps({
                                "job_id": job["id"],
                                "title": job["title"],
                                "location": job["location"],
                                "department": job["department"],
                                "content_preview": (job["content"] or "")[:500] if job.get("content") else None,
                            }),
                        ))
                else:
                    from ..models import SourceRecord
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="greenhouse",
                        source_url=f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs",
                        retrieved_at=datetime.now(timezone.utc),
                        status="success_empty",
                        error_message="No current job postings found",
                    ))

            return self._make_result(
                status=ConnectorStatus.SUCCESS_WITH_RESULTS if enriched_count > 0 else ConnectorStatus.SUCCESS_EMPTY,
                candidates=[],
                request_meta={"company_ids": company_ids, "total_jobs_found": total_jobs},
            )

    def _get_known_board_token(self, company) -> Optional[str]:
        """Get known board token for a company.
        In production, this would come from a verified source or database lookup.
        For testing, we check against known public boards.
        """
        # Check if company domain matches a known board
        if company.website_domain:
            domain = company.website_domain.lower()
            for name, token in KNOWN_GREENHOUSE_BOARDS.items():
                if name in domain:
                    return token

        # Check canonical name
        name_lower = company.canonical_name.lower()
        for name, token in KNOWN_GREENHOUSE_BOARDS.items():
            if name in name_lower:
                return token

        return None

    async def _fetch_jobs(self, board_token: str) -> list[dict]:
        """Fetch jobs from a Greenhouse board."""
        url = f"{self.BASE_URL}/{board_token}/jobs"
        params = {"render_as": "json"}

        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout))
                response = await client.get(url, params=params)
                await client.aclose()

                if response.status_code == 429:
                    await asyncio.sleep(2**attempt)
                    continue

                if response.status_code == 404:
                    return []  # Board not found

                if response.status_code >= 500:
                    await asyncio.sleep(2**attempt)
                    continue

                response.raise_for_status()
                data = response.json()
                return self._parse_jobs(data)

            except httpx.TimeoutException:
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

        return []

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """Greenhouse doesn't do discovery."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="Greenhouse connector does not support discovery",
        )


# Singleton
_greenhouse_connector: Optional[GreenhouseConnector] = None


def get_greenhouse_connector() -> GreenhouseConnector:
    """Get or create the Greenhouse connector singleton."""
    global _greenhouse_connector
    if _greenhouse_connector is None:
        _greenhouse_connector = GreenhouseConnector()
    return _greenhouse_connector