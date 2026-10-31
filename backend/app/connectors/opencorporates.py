"""OpenCorporates connector for business registry data.

Docs: https://api.opencorporates.com/documentation/API-Reference
"""

from __future__ import annotations

import asyncio
import os
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


# OpenCorporates API base URL
OPENCORPORATES_BASE_URL = "https://api.opencorporates.com/v0.4"


class OpenCorporatesConnector(BaseConnector):
    """OpenCorporates connector for business registry data.

    Requires API key and appropriate plan. Implements not_configured
    state if no valid key is provided.
    """

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
        return "open_corporates"

    @property
    def provider(self) -> str:
        return "opencorporates"

    @property
    def role(self) -> ConnectorRole:
        return ConnectorRole.BOTH

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

    def _is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """Enrich companies by looking up OpenCorporates records."""
        from ..models import Company, SourceRecord
        from ..db import session_scope

        request_meta = {"company_ids": company_ids}

        if not company_ids:
            return self._make_result(
                status=ConnectorStatus.SUCCESS_EMPTY,
                candidates=[],
                request_meta=request_meta,
            )

        if not self._is_configured():
            # Mark all companies as not_configured
            with session_scope() as db:
                companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
                for company in companies:
                    db.add(SourceRecord(
                        company_id=company.id,
                        source_type="enrichment",
                        provider="opencorporates",
                        source_url=None,
                        retrieved_at=datetime.now(timezone.utc),
                        status="not_configured",
                        error_message="OpenCorporates API key not configured",
                    ))

            return self._make_result(
                status=ConnectorStatus.NOT_CONFIGURED,
                candidates=[],
                error_code="not_configured",
                error_message="OpenCorporates API key not configured",
                request_meta=request_meta,
            )

        # Real implementation would go here when API key is available
        # For now, return not_configured
        with session_scope() as db:
            companies = db.query(Company).filter(Company.id.in_(company_ids)).all()
            for company in companies:
                db.add(SourceRecord(
                    company_id=company.id,
                    source_type="enrichment",
                    provider="opencorporates",
                    source_url=None,
                    retrieved_at=datetime.now(timezone.utc),
                    status="not_configured",
                    error_message="OpenCorporates API key not configured",
                ))

        return self._make_result(
            status=ConnectorStatus.NOT_CONFIGURED,
            candidates=[],
            error_code="not_configured",
            error_message="OpenCorporates API key not configured",
            request_meta={"company_ids": company_ids},
        )

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        """OpenCorporates can do discovery if configured."""
        if not self._is_configured():
            return self._make_result(
                status=ConnectorStatus.NOT_CONFIGURED,
                candidates=[],
                error_code="not_configured",
                error_message="OpenCorporates API key not configured",
                request_meta={"query": str(query)},
            )

        # Real implementation would go here
        return self._make_result(
            status=ConnectorStatus.NOT_CONFIGURED,
            candidates=[],
            error_code="not_configured",
            error_message="OpenCorporates API key not configured",
            request_meta={"query": str(query)},
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


# Singleton
_opencorporates_connector: Optional[OpenCorporatesConnector] = None


def get_opencorporates_connector() -> OpenCorporatesConnector:
    """Get or create the OpenCorporates connector singleton."""
    global _opencorporates_connector
    if _opencorporates_connector is None:
        api_key = os.getenv("OPENCORPORATES_API_KEY", "").strip()
        _opencorporates_connector = OpenCorporatesConnector(
            api_key=api_key if api_key else None,
        )
    return _opencorporates_connector