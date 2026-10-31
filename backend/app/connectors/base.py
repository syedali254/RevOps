"""Connector interface and base classes.

All source connectors implement this interface. The workflow — not the connector —
decides when each connector runs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional


class ConnectorStatus(str, Enum):
    """Explicit status for every connector result.

    - SUCCESS_WITH_RESULTS: provider responded with at least one candidate/record
    - SUCCESS_EMPTY: provider responded successfully but returned no results
    - NOT_CONFIGURED: connector has no API key or is explicitly disabled
    - UNSUPPORTED: provider does not support the requested query type
    - FAILED: provider error (timeout, rate limit, auth error, parsing failure, etc.)
    """

    SUCCESS_WITH_RESULTS = "success_with_results"
    SUCCESS_EMPTY = "success_empty"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ConnectorRole(str, Enum):
    """The role this connector plays in the hybrid workflow."""

    DISCOVERY = "discovery"
    ENRICHMENT = "enrichment"
    BOTH = "both"


@dataclass(frozen=True)
class ConnectorResult:
    """Standardized result returned by every connector."""

    source_type: str  # e.g., "web_search", "company_website", "job_postings"
    provider: str  # e.g., "brave", "greenhouse", "gnews"
    role: ConnectorRole
    status: ConnectorStatus
    # Candidate companies (for discovery) or enrichment records (for enrichment)
    candidates: list["CandidateCompany"] = field(default_factory=list)
    # For enrichment: which company these records belong to
    company_id: Optional[int] = None
    # Raw provider response for debugging/audit
    raw_response: Optional[dict[str, Any]] = None
    # Error details when status == FAILED
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    # Retrieval timestamp (set by the connector)
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Request metadata for debugging
    request_meta: dict[str, Any] = field(default_factory=dict)

    def is_success(self) -> bool:
        return self.status in (ConnectorStatus.SUCCESS_WITH_RESULTS, ConnectorStatus.SUCCESS_EMPTY)


@dataclass(frozen=True)
class CandidateCompany:
    """A discovered candidate company from a discovery connector."""

    # Core identity fields
    name: str
    website_domain: Optional[str] = None
    # Location
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    # Industry/size
    sector: Optional[str] = None
    employee_min: Optional[int] = None
    employee_max: Optional[int] = None
    # Evidence
    source_url: Optional[str] = None
    snippet: Optional[str] = None
    # Provider-specific metadata
    provider_meta: dict[str, Any] = field(default_factory=dict)

    def normalized_domain(self) -> Optional[str]:
        if not self.website_domain:
            return None
        domain = self.website_domain.strip().lower()
        domain = domain.removeprefix("https://").removeprefix("http://")
        domain = domain.split("/")[0].split("?")[0].split("#")[0]
        return domain or None


class BaseConnector(ABC):
    """Abstract base class for all connectors."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Unique identifier for this source type."""

    @property
    @abstractmethod
    def provider(self) -> str:
        """Provider name (e.g., 'brave', 'greenhouse')."""

    @property
    @abstractmethod
    def role(self) -> ConnectorRole:
        """Whether this is a discovery, enrichment, or both connector."""

    @abstractmethod
    async def discover(self, query: "DiscoveryQuery") -> ConnectorResult:
        """Discover candidate companies matching the query.

        Only called for connectors with role DISCOVERY or BOTH.
        """

    @abstractmethod
    async def enrich(self, company_ids: list[int], query: "EnrichmentQuery") -> ConnectorResult:
        """Enrich already-discovered companies.

        Only called for connectors with role ENRICHMENT or BOTH.
        """

    def _make_result(
        self,
        status: ConnectorStatus,
        candidates: list[CandidateCompany] | None = None,
        company_id: Optional[int] = None,
        raw_response: Optional[dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        request_meta: dict[str, Any] | None = None,
    ) -> ConnectorResult:
        return ConnectorResult(
            source_type=self.source_type,
            provider=self.provider,
            role=self.role,
            status=status,
            candidates=candidates or [],
            company_id=company_id,
            raw_response=raw_response,
            error_code=error_code,
            error_message=error_message,
            request_meta=request_meta or {},
        )


@dataclass(frozen=True)
class DiscoveryQuery:
    """Query parameters for discovery connectors."""

    campaign_id: int
    countries: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    employee_min: Optional[int] = None
    employee_max: Optional[int] = None
    max_results: int = 50
    # Provider-specific parameters
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnrichmentQuery:
    """Query parameters for enrichment connectors."""

    campaign_id: int
    company_ids: list[int]
    domains: list[str] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    # Provider-specific parameters
    extra: dict[str, Any] = field(default_factory=dict)


def is_configured(connector: BaseConnector) -> bool:
    """Check if a connector has the required credentials."""
    return bool(connector.api_key and connector.api_key.strip())


def get_connector_status(connector: BaseConnector) -> ConnectorStatus:
    """Get the static status of a connector (without making a request)."""
    if not is_configured(connector):
        return ConnectorStatus.NOT_CONFIGURED
    return ConnectorStatus.SUCCESS_EMPTY  # Will be updated after actual request