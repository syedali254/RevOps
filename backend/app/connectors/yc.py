"""Y Combinator company directory connector.

Role: DISCOVERY (via CSV import only).

No permitted automated API or CSV export is available at ycombinator.com.
robots.txt disallows access to /companies?*.

This connector provides a CSV import path for users who have legally
obtained YC company data (e.g., through manual export or permitted dataset).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
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


@dataclass
class YCCompanyCSVRow:
    """Expected CSV columns for YC company import."""
    name: str
    website: str
    description: str
    industry: str
    location: str
    batch: str
    employee_min: Optional[int] = None
    employee_max: Optional[int] = None


class YCDirectoryConnector(BaseConnector):
    """Y Combinator company directory connector.

    Does not implement live discovery (no permitted automated access).
    Provides CSV import functionality for legally obtained YC company data.
    """

    SOURCE_TYPE = "yc_directory"
    PROVIDER = "ycombinator"
    ROLE = ConnectorRole.DISCOVERY

    @property
    def source_type(self) -> str:
        return self.SOURCE_TYPE

    @property
    def provider(self) -> str:
        return self.PROVIDER

    @property
    def role(self) -> ConnectorRole:
        return self.ROLE

    def __init__(
        self,
        csv_path: Optional[str] = None,
        csv_content: Optional[str] = None,
        timeout: float = 10.0,
    ):
        super().__init__(api_key=None, timeout=timeout)
        self.csv_path = csv_path
        self.csv_content = csv_content
        self._cached_companies: list[YCCompanyCSVRow] | None = None

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """Import companies from CSV (not live discovery).

        Returns companies from the provided CSV that match campaign criteria.
        """
        request_meta = {
            "csv_path": self.csv_path,
            "has_csv_content": self.csv_content is not None,
            "query_countries": query.countries,
            "query_sectors": query.sectors,
        }

        companies = self._load_companies()
        if companies is None:
            return self._make_result(
                status=ConnectorStatus.NOT_CONFIGURED,
                candidates=[],
                error_code="no_csv_provided",
                error_message="No CSV file or content provided for YC directory import",
                request_meta=request_meta,
            )

        # Filter by campaign criteria
        filtered = self._filter_companies(companies, query)
        candidates = [self._to_candidate(c) for c in filtered]

        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS if candidates else ConnectorStatus.SUCCESS_EMPTY,
            candidates=candidates,
            request_meta=request_meta,
        )

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """YC directory does not support enrichment."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="YC directory connector does not support enrichment",
        )

    def _load_companies(self) -> list[YCCompanyCSVRow] | None:
        """Load companies from CSV file or content."""
        if self._cached_companies is not None:
            return self._cached_companies

        csv_text = None
        if self.csv_content:
            csv_text = self.csv_content
        elif self.csv_path:
            try:
                with open(self.csv_path, "r", encoding="utf-8") as f:
                    csv_text = f.read()
            except Exception as e:
                return None

        if not csv_text:
            return None

        companies = []
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            # Normalize column names (lowercase, strip)
            reader.fieldnames = [fn.strip().lower().replace(" ", "_") for fn in reader.fieldnames or []]

            for row in reader:
                # Try to parse employee range
                emp_min = None
                emp_max = None
                emp_str = row.get("employee_count", "") or row.get("employees", "") or row.get("team_size", "")
                if emp_str:
                    try:
                        if "-" in emp_str:
                            parts = emp_str.split("-")
                            emp_min = int(parts[0].strip())
                            emp_max = int(parts[1].strip())
                        else:
                            emp_min = int(emp_str.strip())
                            emp_max = emp_min
                    except (ValueError, IndexError):
                        pass

                companies.append(YCCompanyCSVRow(
                    name=row.get("name", "").strip(),
                    website=row.get("website", "").strip(),
                    description=row.get("description", "").strip(),
                    industry=row.get("industry", "").strip(),
                    location=row.get("location", "").strip(),
                    batch=row.get("batch", "").strip(),
                    employee_min=emp_min,
                    employee_max=emp_max,
                ))
        except Exception:
            return None

        self._cached_companies = companies
        return companies

    def _filter_companies(self, companies: list[YCCompanyCSVRow], query: DiscoveryQuery) -> list[YCCompanyCSVRow]:
        """Filter companies by campaign criteria."""
        filtered = []

        query_countries = [c.strip().lower() for c in query.countries]
        query_sectors = [s.strip().lower() for s in query.sectors]

        # US state abbreviations and common city names for US location detection
        us_states = {
            "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id",
            "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms",
            "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok",
            "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv",
            "wi", "wy", "dc"
        }
        us_cities = {
            "san francisco", "new york", "boston", "seattle", "austin", "los angeles",
            "chicago", "denver", "portland", "atlanta", "miami", "dallas", "houston",
            "philadelphia", "phoenix", "san diego", "san jose", "washington", "remote"
        }

        for c in companies:
            if not c.name or not c.website:
                continue

            # Country filter - improved US detection
            if query_countries and c.location:
                location_lower = c.location.lower()
                location_matches = False
                for qc in query_countries:
                    if qc in location_lower:
                        location_matches = True
                        break
                    # Check for US state abbreviations or cities
                    if qc in ("united states", "usa", "us", "america"):
                        # Check for state abbreviation at end of location (e.g., "San Francisco CA")
                        parts = [p.strip() for p in location_lower.replace(",", " ").split()]
                        for part in parts:
                            if part in us_states:
                                location_matches = True
                                break
                        # Check for known US cities
                        if not location_matches:
                            for city in us_cities:
                                if city in location_lower:
                                    location_matches = True
                                    break
                        # "remote" often means US-based for YC companies
                        if "remote" in location_lower:
                            location_matches = True
                if not location_matches:
                    continue

            # Sector/industry filter
            if query_sectors and c.industry:
                industry_lower = c.industry.lower()
                if not any(qs in industry_lower for qs in query_sectors):
                    continue

            # Employee range filter
            if query.employee_min is not None and c.employee_max is not None:
                if c.employee_max < query.employee_min:
                    continue
            if query.employee_max is not None and c.employee_min is not None:
                if c.employee_min > query.employee_max:
                    continue

            filtered.append(c)

            if len(filtered) >= query.max_results:
                break

        return filtered

    def _to_candidate(self, company: YCCompanyCSVRow) -> CandidateCompany:
        """Convert CSV row to CandidateCompany."""
        domain = company.website
        if domain:
            domain = domain.strip().lower()
            domain = domain.removeprefix("https://").removeprefix("http://")
            domain = domain.split("/")[0].split("?")[0].split("#")[0]

        return CandidateCompany(
            name=company.name,
            website_domain=domain or None,
            country=company.location or None,
            sector=company.industry or None,
            employee_min=company.employee_min,
            employee_max=company.employee_max,
            source_url=f"https://www.ycombinator.com/companies/{company.name.lower().replace(' ', '-')}",
            snippet=company.description[:500] if company.description else None,
            provider_meta={
                "yc_batch": company.batch,
                "yc_industry": company.industry,
                "import_method": "csv",
            },
        )

    @classmethod
    def get_csv_template(cls) -> str:
        """Return a CSV template string for users."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "name", "website", "description", "industry", "location", "batch",
            "employee_count"
        ])
        writer.writerow([
            "Example Company", "https://example.com", "AI-powered analytics platform",
            "B2B Software", "San Francisco, CA", "W24", "25-50"
        ])
        return output.getvalue()


# Singleton
_yc_connector: Optional[YCDirectoryConnector] = None


def get_yc_connector(
    csv_path: Optional[str] = None,
    csv_content: Optional[str] = None,
) -> YCDirectoryConnector:
    """Get or create the YC directory connector singleton."""
    global _yc_connector
    if _yc_connector is None:
        _yc_connector = YCDirectoryConnector(csv_path=csv_path, csv_content=csv_content)
    return _yc_connector