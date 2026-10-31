"""SEC EDGAR connector for public company filings.

Docs: https://www.sec.gov/edgar/sec-api-documentation
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import httpx


def _parse_filing_date(date_str: str | None) -> datetime | None:
    """Parse SEC filing date string (YYYY-MM-DD) to datetime."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except Exception:
        return None

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


# SEC EDGAR base URLs
SEC_BASE_URL = "https://data.sec.gov"
SEC_SUBMISSIONS_URL = f"{SEC_BASE_URL}/submissions"
SEC_COMPANY_FACTS_URL = f"{SEC_BASE_URL}/api/xbrl/companyfacts"


@dataclass
class SECFiling:
    """An SEC filing record."""
    accession_number: str
    filing_date: str
    report_date: Optional[str]
    form: str
    primary_document: Optional[str]
    primary_doc_description: Optional[str]


class SECEdgarConnector(BaseConnector):
    """SEC EDGAR connector for public company filings.

    Uses official SEC public endpoints. No API key required but requires
    a descriptive User-Agent per SEC fair access policy.
    """

    def __init__(
        self,
        timeout: float = 20.0,
        max_retries: int = 2,
        user_agent: str = "B2BLeadEngine/1.0 (contact@example.com) - SEC EDGAR research",
    ):
        super().__init__(api_key=None, timeout=timeout)
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_type(self) -> str:
        return "sec_edgar"

    @property
    def provider(self) -> str:
        return "sec"

    @property
    def role(self) -> ConnectorRole:
        return ConnectorRole.BOTH  # Can discover (via CIK lookup) and enrich

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "User-Agent": self.user_agent,
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _normalize_cik(self, cik: str) -> str:
        """Normalize CIK to 10-digit zero-padded string."""
        digits = re.sub(r"\D", "", cik)
        return digits.zfill(10)

    async def _get_company_cik(self, company_name: str, domain: Optional[str]) -> Optional[str]:
        """Look up CIK for a company name using SEC's company tickers endpoint."""
        # SEC provides a static JSON file with all company tickers and CIKs
        # https://www.sec.gov/files/company_tickers.json
        try:
            client = await self._get_client()
            response = await client.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": self.user_agent},
            )
            if response.status_code == 200:
                data = response.json()
                # Search for matching company name or ticker
                name_lower = company_name.lower()
                for entry in data.values():
                    if isinstance(entry, dict):
                        title = entry.get("title", "").lower()
                        ticker = entry.get("ticker", "").lower()
                        cik = str(entry.get("cik_str", "")).zfill(10)
                        if (company_name.lower() in title or
                            title in company_name.lower() or
                            (entry.get("ticker") and entry["ticker"].lower() == company_name.lower())):
                            return cik
        except Exception:
            pass
        return None

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Enrich companies by looking up SEC filings."""
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

        with session_scope() as db:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()

            for company in companies:
                cik = None

                # Try to find CIK
                cik = await self._get_company_cik(company.canonical_name, company.website_domain)

                if not cik:
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="sec",
                        source_url=None,
                        retrieved_at=datetime.now(timezone.utc),
                        status="unsupported",
                        error_message="Company not found in SEC EDGAR (likely not a public filer)",
                    ))
                    continue

                # Fetch recent filings
                filings = await self._get_filings(cik)

                if filings:
                    enriched_count += 1
                    # Store recent filings as source records
                    for filing in filings[:10]:  # Limit to 10 most recent
                        db.add(SourceRecord(
                            company_id=company.id,
                            source_type="enrichment",
                            provider="sec",
                            source_url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{filing.accession_number.replace('-', '')}/{filing.primary_document}" if filing.primary_document else None,
                            retrieved_at=datetime.now(timezone.utc),
                            published_at=_parse_filing_date(filing.filing_date),
                            status="success_with_results",
                            raw_payload_json=__import__("json").dumps({
                                "accession_number": filing.accession_number,
                                "filing_date": filing.filing_date,
                                "report_date": filing.report_date,
                                "form": filing.form,
                                "primary_document": filing.primary_document,
                                "primary_doc_description": filing.primary_doc_description,
                                "cik": cik,
                            }),
                        ))
                else:
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="sec",
                        source_url=f"{SEC_SUBMISSIONS_URL}/CIK{cik}.json",
                        retrieved_at=datetime.now(timezone.utc),
                        status="success_empty",
                        error_message="No recent filings found",
                    ))

        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS if enriched_count > 0 else ConnectorStatus.SUCCESS_EMPTY,
            candidates=[],
            request_meta={"company_ids": company_ids},
        )

    async def _get_filings(self, cik: str) -> list:
        """Fetch recent filings for a CIK."""
        normalized_cik = self._normalize_cik(cik)
        url = f"{SEC_SUBMISSIONS_URL}/CIK{normalized_cik}.json"

        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.get(url)
                if response.status_code == 404:
                    return []
                if response.status_code == 429:
                    await asyncio.sleep(2**attempt)
                    continue
                if response.status_code >= 500:
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                data = response.json()

                # Parse recent filings
                filings_data = data.get("filings", {}).get("recent", {})
                filings = []
                for i in range(len(filings_data.get("accessionNumber", []))):
                    filings.append({
                        "accession_number": filings_data["accessionNumber"][i],
                        "filing_date": filings_data["filingDate"][i],
                        "report_date": filings_data.get("reportDate", [None]*len(filings_data["accessionNumber"]))[i],
                        "form": filings_data["form"][i],
                        "primary_document": filings_data["primaryDocument"][i] if filings_data.get("primaryDocument") else None,
                        "primary_doc_description": filings_data["primaryDocDescription"][i] if filings_data.get("primaryDocDescription") else None,
                    })
                return filings

            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                continue
            except httpx.RequestError:
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                continue
            except Exception:
                break

        return []

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "B2BLeadEngine/1.0 (contact@example.com) - SEC EDGAR research",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Enrich companies by looking up SEC filings."""
        from ..models import Company, SourceRecord
        from ..db import session_scope

        request_meta = {"company_ids": company_ids}

        if not company_ids:
            return self._make_result(
                status=ConnectorStatus.SUCCESS_EMPTY,
                candidates=[],
                request_meta=request_meta,
            )

        enriched_count = 0

        with session_scope() as db:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()

            for company in companies:
                cik = await self._get_company_cik(company.canonical_name, company.website_domain)

                if not cik:
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="sec",
                        source_url=None,
                        retrieved_at=datetime.now(timezone.utc),
                        status="unsupported",
                        error_message="Company not found in SEC EDGAR (likely not a public filer)",
                    ))
                    continue

                filings = await self._get_filings(cik)

                if filings:
                    enriched_count += 1
                    for filing in filings[:10]:
                        db.add(SourceRecord(
                            company_id=company.id,
                            source_type="enrichment",
                            provider="sec",
                            source_url=f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{filing['accession_number'].replace('-', '')}/{filing.get('primary_document', '')}" if filing.get('primary_document') else None,
                            retrieved_at=datetime.now(timezone.utc),
                            published_at=_parse_filing_date(filing.get('filing_date')),
                            status="success_with_results",
                            raw_payload_json=__import__("json").dumps({
                                "accession_number": filing["accession_number"],
                                "filing_date": filing["filing_date"],
                                "report_date": filing.get("report_date"),
                                "form": filing["form"],
                                "primary_document": filing.get("primary_document"),
                                "primary_doc_description": filing.get("primary_doc_description"),
                                "cik": cik,
                            }),
                        ))
                else:
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="sec",
                        source_url=f"https://data.sec.gov/submissions/CIK{cik}.json",
                        retrieved_at=datetime.now(timezone.utc),
                        status="success_empty",
                        error_message="No recent filings found",
                    ))

        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS if enriched_count > 0 else ConnectorStatus.SUCCESS_EMPTY,
            candidates=[],
            request_meta={"company_ids": company_ids},
        )

    async def _get_company_cik(self, company_name: str, domain: Optional[str]) -> Optional[str]:
        """Look up CIK for a company name using SEC's company tickers endpoint."""
        try:
            client = await self._get_client()
            response = await client.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers={"User-Agent": "B2BLeadEngine/1.0 (contact@example.com) - SEC EDGAR research"},
            )
            if response.status_code == 200:
                data = response.json()
                name_lower = company_name.lower()
                for entry in data.values():
                    if isinstance(entry, dict):
                        title = entry.get("title", "").lower()
                        ticker = entry.get("ticker", "").lower()
                        cik = str(entry.get("cik_str", "")).zfill(10)
                        if (company_name.lower() in title or
                            title in company_name.lower() or
                            (entry.get("ticker") and entry["ticker"].lower() == company_name.lower())):
                            return cik
        except Exception:
            pass
        return None

    async def _get_filings(self, cik: str) -> list:
        """Fetch recent filings for a CIK."""
        normalized_cik = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{normalized_cik}.json"

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                    response = await client.get(url, headers={"User-Agent": "B2BLeadEngine/1.0 (contact@example.com)"})
                    if response.status_code == 404:
                        return []
                    if response.status_code == 429:
                        await asyncio.sleep(2**attempt)
                        continue
                    if response.status_code >= 500:
                        await asyncio.sleep(2**attempt)
                        continue
                    response.raise_for_status()
                    data = response.json()

                    filings_data = data.get("filings", {}).get("recent", {})
                    filings = []
                    for i in range(len(filings_data.get("accessionNumber", []))):
                        filings.append({
                            "accession_number": filings_data["accessionNumber"][i],
                            "filing_date": filings_data["filingDate"][i],
                            "report_date": filings_data.get("reportDate", [None]*len(filings_data["accessionNumber"]))[i],
                            "form": filings_data["form"][i],
                            "primary_document": filings_data["primaryDocument"][i] if filings_data.get("primaryDocument") else None,
                            "primary_doc_description": filings_data["primaryDocDescription"][i] if filings_data.get("primaryDocDescription") else None,
                        })
                    return filings

            except Exception:
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                continue

        return []

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """SEC EDGAR doesn't do broad discovery."""
        return self._make_result(
            status=ConnectorStatus.UNSUPPORTED,
            candidates=[],
            error_code="unsupported_operation",
            error_message="SEC EDGAR connector does not support broad discovery",
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Singleton
_sec_connector: Optional[SECEdgarConnector] = None


def get_sec_connector() -> SECEdgarConnector:
    """Get or create the SEC EDGAR connector singleton."""
    global _sec_connector
    if _sec_connector is None:
        _sec_connector = SECEdgarConnector()
    return _sec_connector