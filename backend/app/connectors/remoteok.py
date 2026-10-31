"""Remote OK public job feed connector.

Role: DISCOVERY + BUSINESS SIGNALS.

Uses the official public JSON feed at https://remoteok.com/api

Official feed terms:
- Must link back to Remote OK with follow (no nofollow)
- Must mention Remote OK as source
- Do not use Remote OK logo without permission

This connector parses the feed to discover companies and extract hiring signals.
"""

from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

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
class RemoteOKJob:
    """A job posting from Remote OK."""
    id: str
    slug: str
    epoch: int
    date: str
    company: str
    company_logo: str
    position: str
    tags: list[str]
    description: str
    location: str
    apply_url: str
    salary_min: int
    salary_max: int
    url: str


class RemoteOKConnector(BaseConnector):
    """Remote OK public job feed connector.

    Fetches the public JSON feed and extracts company/hiring signals.
    """

    BASE_URL = "https://remoteok.com/api"
    SOURCE_TYPE = "remoteok_jobs"
    PROVIDER = "remoteok"
    ROLE = ConnectorRole.DISCOVERY

    def __init__(
        self,
        timeout: float = 15.0,
        max_retries: int = 2,
        max_jobs: int = 500,
    ):
        super().__init__(api_key=None, timeout=timeout)
        self.max_retries = max_retries
        self.max_jobs = max_jobs
        self._client: Optional[httpx.AsyncClient] = None
        self._cached_jobs: list[RemoteOKJob] | None = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes cache

    @property
    def source_type(self) -> str:
        return self.SOURCE_TYPE

    @property
    def provider(self) -> str:
        return self.PROVIDER

    @property
    def role(self) -> ConnectorRole:
        return self.ROLE

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "B2BLeadEngine/1.0 (+https://github.com/b2b-lead-engine; source=remoteok)",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _fetch_feed(self) -> list[RemoteOKJob]:
        """Fetch and parse the Remote OK feed with caching."""
        now = datetime.now(timezone.utc)
        if (
            self._cached_jobs is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < self._cache_ttl_seconds
        ):
            return self._cached_jobs

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.get(self.BASE_URL)

                if response.status_code == 429:
                    retry_after = response.headers.get("retry-after")
                    wait_time = int(retry_after) if retry_after and retry_after.isdigit() else (2 ** attempt)
                    await asyncio.sleep(wait_time)
                    continue

                if response.status_code >= 500:
                    await asyncio.sleep(2 ** attempt)
                    continue

                response.raise_for_status()
                data = response.json()

                # Parse jobs (first item is metadata)
                jobs = []
                for item in data[1:]:
                    if not isinstance(item, dict):
                        continue
                    job = self._parse_job(item)
                    if job:
                        jobs.append(job)

                self._cached_jobs = jobs[:self.max_jobs]
                self._cache_time = now
                return self._cached_jobs

            except httpx.TimeoutException:
                last_error = "timeout"
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                continue
            except httpx.RequestError as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                continue
            except Exception as e:
                last_error = str(e)
                break

        # All retries failed
        raise Exception(f"Failed to fetch Remote OK feed after {self.max_retries + 1} attempts: {last_error}")

    def _parse_job(self, item: dict[str, Any]) -> Optional[RemoteOKJob]:
        """Parse a single job item from the feed."""
        try:
            # Required fields
            company = item.get("company", "").strip()
            position = item.get("position", "").strip()
            if not company or not position:
                return None

            # Clean HTML from description
            description = item.get("description", "")
            clean_description = self._clean_html(description) if description else ""

            return RemoteOKJob(
                id=str(item.get("id", "")),
                slug=item.get("slug", ""),
                epoch=item.get("epoch", 0),
                date=item.get("date", ""),
                company=company,
                company_logo=item.get("company_logo", ""),
                position=position,
                tags=item.get("tags", []) or [],
                description=clean_description,
                location=item.get("location", "") or "",
                apply_url=item.get("apply_url", ""),
                salary_min=item.get("salary_min", 0) or 0,
                salary_max=item.get("salary_max", 0) or 0,
                url=item.get("url", ""),
            )
        except Exception:
            return None

    def _clean_html(self, html_text: str) -> str:
        """Basic HTML cleaning."""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html_text)
        # Decode HTML entities
        text = html.unescape(text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain or None
        except Exception:
            return None

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """Discover companies from Remote OK job feed."""
        request_meta = {
            "query_countries": query.countries,
            "query_sectors": query.sectors,
            "max_results": query.max_results,
        }

        try:
            jobs = await self._fetch_feed()
        except Exception as e:
            return self._make_result(
                status=ConnectorStatus.FAILED,
                candidates=[],
                error_code="fetch_failed",
                error_message=f"Failed to fetch Remote OK feed: {e}",
                request_meta=request_meta,
            )

        # Group jobs by company
        company_jobs: dict[str, list[RemoteOKJob]] = {}
        for job in jobs:
            company_key = job.company.strip().lower()
            if company_key not in company_jobs:
                company_jobs[company_key] = []
            company_jobs[company_key].append(job)

        # Filter companies by campaign criteria
        filtered_companies = []
        query_countries = [c.strip().lower() for c in query.countries]
        query_sectors = [s.strip().lower() for s in query.sectors]

        # Sector/tech keywords from tags
        tech_keywords = {
            "golang", "go", "python", "javascript", "typescript", "react", "vue", "node",
            "aws", "gcp", "azure", "kubernetes", "docker", "terraform", "postgres",
            "mysql", "redis", "kafka", "elasticsearch", "graphql", "rest", "api",
            "saas", "fintech", "healthtech", "edtech", "biotech", "ai", "ml", "data",
            "devops", "sre", "backend", "frontend", "fullstack", "mobile", "ios", "android"
        }

        for company_key, jobs_list in company_jobs.items():
            if len(filtered_companies) >= query.max_results:
                break

            # Use first job as representative
            job = jobs_list[0]
            company_name = job.company.strip()

            # Check tags for relevance
            job_tags = [t.strip().lower() for t in job.tags]
            has_tech_tag = any(tag in tech_keywords for tag in job_tags)

            # If no tech tag but we have sectors to match, check if position matches
            if not has_tech_tag and query_sectors:
                position_lower = job.position.lower()
                has_tech_tag = any(qs in position_lower for qs in query_sectors)

            if not has_tech_tag and query_sectors:
                continue

            # Location check (Remote OK is remote-first, but some have location)
            if query_countries and job.location:
                location_lower = job.location.lower()
                if not any(c in location_lower for c in query_countries):
                    # Still include if remote, since they could work from target country
                    if "remote" not in location_lower and "worldwide" not in location_lower:
                        continue

            # Build candidate
            domain = None
            # Try to extract domain from apply_url or company name heuristic
            if job.apply_url:
                domain = self._extract_domain(job.apply_url)

            # Combine tags from all jobs for this company
            all_tags = set()
            for j in jobs_list:
                all_tags.update(t.strip().lower() for t in j.tags)
            sector = ", ".join(sorted(all_tags)[:5]) if all_tags else "technology"

            # Employee range heuristic from job count
            emp_min = min(len(jobs_list) * 2, 10) if jobs_list else None
            emp_max = len(jobs_list) * 5 if jobs_list else None

            candidate = CandidateCompany(
                name=company_name,
                website_domain=domain,
                country="United States" if "united states" in (job.location or "").lower() else None,
                sector=sector,
                employee_min=emp_min,
                employee_max=emp_max,
                source_url=job.url or job.apply_url,
                snippet=f"Hiring: {job.position} ({len(jobs_list)} open roles). Tags: {', '.join(job.tags[:5])}",
                provider_meta={
                    "job_count": len(jobs_list),
                    "sample_job": job.position,
                    "sample_tags": job.tags[:5],
                    "job_url": job.url,
                    "apply_url": job.apply_url,
                    "posted_date": job.date,
                },
            )
            filtered_companies.append(candidate)

        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS if filtered_companies else ConnectorStatus.SUCCESS_EMPTY,
            candidates=filtered_companies,
            request_meta=request_meta,
        )

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Enrich known companies by finding their Remote OK job postings.

        This can be used to verify hiring signals for already-discovered companies.
        """
        request_meta = {
            "company_ids": company_ids,
        }

        if not company_ids:
            return self._make_result(
                status=ConnectorStatus.SUCCESS_EMPTY,
                candidates=[],
                request_meta=request_meta,
            )

        try:
            jobs = await self._fetch_feed()
        except Exception as e:
            return self._make_result(
                status=ConnectorStatus.FAILED,
                candidates=[],
                error_code="fetch_failed",
                error_message=f"Failed to fetch Remote OK feed: {e}",
                request_meta=request_meta,
            )

        # Load companies from DB to get their names/domains
        from ..models import Company
        from ..db import session_scope

        company_names = set()
        company_domains = set()

        with session_scope() as db:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
            for c in companies:
                if c.canonical_name:
                    company_names.add(c.canonical_name.strip().lower())
                if c.website_domain:
                    company_domains.add(c.website_domain.strip().lower())

        # Find matching jobs
        matched_jobs = []
        for job in jobs:
            if job.company.strip().lower() in company_names:
                matched_jobs.append(job)
            elif job.apply_url:
                job_domain = self._extract_domain(job.apply_url)
                if job_domain and job_domain in company_domains:
                    matched_jobs.append(job)

        if not matched_jobs:
            return self._make_result(
                status=ConnectorStatus.SUCCESS_EMPTY,
                candidates=[],
                request_meta={"company_ids": company_ids, "jobs_found": 0},
            )

        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS,
            candidates=[],  # Enrichment doesn't return candidates
            request_meta={
                "company_ids": company_ids,
                "jobs_found": len(matched_jobs),
                "positions": [j.position for j in matched_jobs[:10]],
            },
        )


# Singleton
_remoteok_connector: Optional[RemoteOKConnector] = None


def get_remoteok_connector() -> RemoteOKConnector:
    """Get or create the Remote OK connector singleton."""
    global _remoteok_connector
    if _remoteok_connector is None:
        _remoteok_connector = RemoteOKConnector()
    return _remoteok_connector