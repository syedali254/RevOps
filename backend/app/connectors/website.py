"""Company website enrichment connector.

Fetches and extracts information from a company's official website.
"""

from __future__ import annotations

import asyncio
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

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
from app.models import Company, SourceRecord


# Common paths to try on company websites
COMMON_PATHS = [
    "/",
    "/about",
    "/about-us",
    "/company",
    "/who-we-are",
    "/our-story",
    "/products",
    "/services",
    "/solutions",
    "/technology",
    "/platform",
    "/careers",
    "/jobs",
    "/contact",
    "/contact-us",
    "/news",
    "/press",
    "/blog",
    "/resources",
]


@dataclass
class EnrichedField:
    """A single enriched field with evidence."""
    field_name: str
    value: str
    source_url: str
    snippet: str
    confidence: float  # 0.0 to 1.0


class CompanyWebsiteConnector(BaseConnector):
    """Fetches and extracts company information from official websites."""

    def __init__(
        self,
        timeout: float = 15.0,
        max_pages: int = 8,
        max_retries: int = 2,
        user_agent: str = "B2BLeadEngine/1.0 (+https://github.com/b2b-lead-engine; contact@example.com)",
    ):
        super().__init__(api_key=None, timeout=timeout)
        self.max_pages = max_pages
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_type(self) -> str:
        return "company_website"

    @property
    def provider(self) -> str:
        return "direct_fetch"

    @property
    def role(self) -> ConnectorRole:
        return ConnectorRole.ENRICHMENT

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate",
                },
                follow_redirects=True,
                max_redirects=5,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _is_safe_url(self, url: str, base_domain: str) -> bool:
        """Check if URL is safe to fetch (no SSRF, private IPs, localhost)."""
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            # Block localhost and private IPs
            hostname = parsed.hostname or ""
            if hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
                return False
            # Block private IP ranges
            try:
                import ipaddress
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return False
            except ValueError:
                # Not an IP address, that's fine
                pass
            # Only allow same domain or subdomain
            if not (hostname == base_domain or hostname.endswith("." + base_domain)):
                return False
            return True
        except Exception:
            return False

    def _normalize_domain(self, url: str) -> Optional[str]:
        """Extract and normalize domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain or None
        except Exception:
            return None

    def _extract_text(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """Extract text content using CSS selector."""
        try:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator=" ", strip=True)
                return text[:2000] if text else None
        except Exception:
            pass
        return None

    def _extract_meta(self, soup: BeautifulSoup, name: str) -> Optional[str]:
        """Extract meta tag content."""
        try:
            meta = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
            if meta and meta.get("content"):
                return meta["content"][:500]
        except Exception:
            pass
        return None

    def _extract_json_ld(self, soup: BeautifulSoup) -> list[dict]:
        """Extract JSON-LD structured data."""
        results = []
        try:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, list):
                        results.extend(data)
                    else:
                        results.append(data)
                except Exception:
                    pass
        except Exception:
            pass
        return results

    def _extract_company_info(self, soup: BeautifulSoup, url: str) -> list[EnrichedField]:
        """Extract company information from parsed HTML."""
        fields = []
        base_url = url

        # Try JSON-LD first (structured data)
        for data in self._extract_json_ld(soup):
            if isinstance(data, dict) and data.get("@type") in ("Organization", "Corporation", "LocalBusiness"):
                if data.get("name"):
                    fields.append(EnrichedField(
                        field_name="canonical_name",
                        value=data["name"],
                        source_url=url,
                        snippet=f'JSON-LD Organization name: {data["name"]}',
                        confidence=0.9,
                    ))
                if data.get("url"):
                    fields.append(EnrichedField(
                        field_name="website_domain",
                        value=self._normalize_domain(data["url"]) or "",
                        source_url=url,
                        snippet=f'JSON-LD URL: {data["url"]}',
                        confidence=0.9,
                    ))
                if data.get("description"):
                    fields.append(EnrichedField(
                        field_name="description",
                        value=data["description"][:500],
                        source_url=url,
                        snippet=data["description"][:200],
                        confidence=0.8,
                    ))
                if data.get("address", {}).get("addressCountry"):
                    fields.append(EnrichedField(
                        field_name="country",
                        value=data["address"]["addressCountry"],
                        source_url=url,
                        snippet=f'JSON-LD country: {data["address"]["addressCountry"]}',
                        confidence=0.7,
                    ))
                if data.get("numberOfEmployees"):
                    emp = data["numberOfEmployees"]
                    if isinstance(emp, dict) and emp.get("@type") == "QuantitativeValue":
                        min_emp = emp.get("minValue")
                        max_emp = emp.get("maxValue")
                        if min_emp is not None:
                            fields.append(EnrichedField(
                                field_name="employee_min",
                                value=str(min_emp),
                                source_url=url,
                                snippet=f'JSON-LD min employees: {min_emp}',
                                confidence=0.7,
                            ))
                        if max_emp is not None:
                            fields.append(EnrichedField(
                                field_name="employee_max",
                                value=str(max_emp),
                                source_url=url,
                                snippet=f'JSON-LD max employees: {max_emp}',
                                confidence=0.7,
                            ))

        # Meta tags
        meta_desc = self._extract_meta(soup, "description") or self._extract_meta(soup, "og:description")
        if meta_desc and not any(f.field_name == "description" for f in fields):
            fields.append(EnrichedField(
                field_name="description",
                value=meta_desc,
                source_url=url,
                snippet=meta_desc[:200],
                confidence=0.6,
            ))

        # Title tag
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Extract company name from title (often "Company Name - Tagline" or "Company Name | Tagline")
            for sep in [" - ", " | ", " â€“ "]:
                if sep in title_text:
                    potential_name = title_text.split(sep)[0].strip()
                    if len(potential_name) > 2 and len(potential_name) < 100:
                        fields.append(EnrichedField(
                            field_name="canonical_name",
                            value=potential_name,
                            source_url=url,
                            snippet=f'Title tag: {title_text}',
                            confidence=0.5,
                        ))
                        break

        # Meta og:site_name
        og_site = self._extract_meta(soup, "og:site_name")
        if og_site and not any(f.field_name == "canonical_name" for f in fields):
            fields.append(EnrichedField(
                field_name="canonical_name",
                value=og_site,
                source_url=url,
                snippet=f'og:site_name: {og_site}',
                confidence=0.6,
            ))

        # Look for common content patterns
        page_text = soup.get_text(separator=" ", strip=True)[:10000]

        # Employee count patterns
        emp_patterns = [
            r'(\d{1,3}(?:,\d{3})?)\s*[-\+]?\s*employees?',
            r'team of\s+(\d{1,3}(?:,\d{3})?)',
            r'(\d{1,3}(?:,\d{3})?)\s+people',
            r'workforce of\s+(\d{1,3}(?:,\d{3})?)',
        ]
        for pattern in emp_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                try:
                    num = int(matches[0].replace(",", ""))
                    if 1 <= num <= 100000:
                        fields.append(EnrichedField(
                            field_name="employee_min",
                            value=str(num),
                            source_url=url,
                            snippet=f'Found employee mention: {matches[0]}',
                            confidence=0.4,
                        ))
                        break
                except ValueError:
                    pass

        # Location patterns
        location_patterns = [
            r'headquartered in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'based in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'located in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        for pattern in location_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            if matches:
                fields.append(EnrichedField(
                    field_name="country",
                    value=matches[0],
                    source_url=url,
                    snippet=f'Location mention: {matches[0]}',
                    confidence=0.4,
                ))
                break

        return fields

    def _get_page_urls(self, base_url: str) -> list[str]:
        """Generate list of URLs to try on the company website."""
        parsed = urllib.parse.urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        urls = [base]
        for path in COMMON_PATHS:
            urls.append(urljoin(base, path))
        return urls[:self.max_pages + 1]

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> Optional[BeautifulSoup]:
        """Fetch a single page and parse with BeautifulSoup."""
        try:
            response = await client.get(url)
            if response.status_code == 200:
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    return BeautifulSoup(response.text, "html.parser")
        except Exception:
            pass
        return None

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Enrich companies by fetching their websites."""
        from ..models import Company, SourceRecord
        from ..db import session_scope

        request_meta = {
            "company_ids": company_ids,
            "domains": query.domains,
            "names": query.names,
        }

        if not company_ids:
            return self._make_result(
                status=ConnectorStatus.SUCCESS_EMPTY,
                candidates=[],
                request_meta=request_meta,
            )

        enriched_count = 0
        failed_count = 0
        all_fields = []

        with session_scope() as db:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()

            for company in companies:
                domain = company.website_domain
                if not domain:
                    # No website domain to enrich from
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="company_website",
                        source_url=None,
                        retrieved_at=datetime.now(timezone.utc),
                        status="success_empty",
                        error_message="No website domain available",
                    ))
                    continue

                base_url = f"https://{domain}"
                urls_to_try = self._get_page_urls(base_url)

                client = await self._get_client()
                company_fields = []
                pages_fetched = 0

                for url in urls_to_try:
                    if pages_fetched >= self.max_pages:
                        break
                    soup = await self._fetch_page(client, url)
                    if soup:
                        fields = self._extract_company_info(soup, url)
                        for field in fields:
                            # Avoid duplicates
                            if not any(f.field_name == field.field_name and f.value == field.value for f in company_fields):
                                company_fields.append(field)
                                all_fields.append({
                                    "company_id": company.id,
                                    "field_name": field.field_name,
                                    "value": field.value,
                                    "source_url": field.source_url,
                                    "snippet": field.snippet,
                                    "confidence": field.confidence,
                                })
                        pages_fetched += 1

                # Store source record for this company
                status = "success_with_results" if company_fields else "success_empty"
                db.add(SourceRecord(
                    company_id=company.id,
                    source_type="enrichment",
                    provider="company_website",
                    source_url=f"https://{domain}",
                    retrieved_at=datetime.now(timezone.utc),
                    raw_payload_json=None,
                    status=status,
                    error_message=None if company_fields else "No extractable content found",
                ))

                if company_fields:
                    enriched_count += 1
                else:
                    failed_count += 1

        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS if enriched_count > 0 else ConnectorStatus.SUCCESS_EMPTY,
            candidates=[],  # Enrichment doesn't return candidates
            request_meta=request_meta,
        )

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """Website connector doesn't do discovery."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="Company website connector does not support discovery",
        )


# Singleton
_website_connector: Optional[CompanyWebsiteConnector] = None


def get_website_connector() -> CompanyWebsiteConnector:
    """Get or create the website connector singleton."""
    global _website_connector
    if _website_connector is None:
        _website_connector = CompanyWebsiteConnector()
    return _website_connector