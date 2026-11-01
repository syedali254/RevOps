"""Hacker News "Who is Hiring" connector.

Role: DISCOVERY only.

Free, public Algolia HN Search API — no API key, no scraping, no login.
Docs: https://hn.algolia.com/api

Data source: the monthly "Ask HN: Who is hiring?" thread, where founders and
hiring managers post their company, location and open roles in a
well-known format:

    "Company name | Location | Role | Extra info"

Sources are attributed: every candidate keeps the comment text and the HN
comment permalink as proof. This is public, self-declared data by the poster,
used read-only through the official search API — no terms violation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
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
)


# Tech/sector keywords used to keep candidates relevant to a B2B tech campaign.
_SECTOR_KEYWORDS = {
    "saas", "b2b", "software", "engineering", "devops", "backend", "frontend",
    "fullstack", "full-stack", "data", "machine learning", "ml", "ai",
    "cloud", "infrastructure", "security", "analytics", "api", "platform",
    "fintech", "healthtech", "edtech", "biotech", "devtools", "database",
}

# Country name → common abbreviations / aliases used inside HN posts.
_COUNTRY_ALIASES = {
    "united states": {"united states", "usa", "u.s.", "us ", "america", "nyc", "new york", "san francisco", "sf ", "seattle", "austin", "boston", "chicago", "los angeles", "denver", "washington dc"},
    "united kingdom": {"united kingdom", "uk ", "london", "england", "scotland", "wales"},
    "canada": {"canada", "toronto", "vancouver", "montreal", "ottawa"},
    "germany": {"germany", "berlin", "munich", "grmany"},
    "india": {"india", "bangalore", "bengaluru", "mumbai", "delhi"},
    "australia": {"australia", "sydney", "melbourne"},
    "france": {"france", "paris"},
    "netherlands": {"netherlands", "amsterdam"},
    "singapore": {"singapore"},
}


# Domains that are never the COMPANY'S own website when seen as the first link
# (recruiting/social pages). A candidate that only links there gets domain=None.
_NON_COMPANY_DOMAINS = {
    "linkedin.com", "wellfound.com", "angellist.com", "glassdoor.com",
    "indeed.com", "x.com", "twitter.com", "facebook.com", "medium.com",
    "github.com", "stackoverflow.com", "remoteok.com", "ycombinator.com",
    "hn.algolia.com", "news.ycombinator.com", "bluesky.com", "discord.com",
    "telegram.me", "youtube.com", "substack.com",
}


@dataclass
class HNHiringPost:
    """One parsed top-level comment from a Who-is-hiring thread."""

    hn_id: int
    company: str
    location: str
    role: str
    domain: Optional[str]
    text_url: Optional[str]          # https://news.ycombinator.com/item?id=...
    snippet: str
    permalink: str                   # full link back to HN (attribution)
    created_at: Optional[datetime]


class HNHiringConnector(BaseConnector):
    """Discovery connector over the monthly Hacker News Who-is-Hiring thread."""

    API_BASE = "https://hn.algolia.com/api/v1"
    SOURCE_TYPE = "hn_hiring"
    PROVIDER = "hn"
    ROLE = ConnectorRole.DISCOVERY

    def __init__(
        self,
        timeout: float = 15.0,
        max_retries: int = 2,
        cache_ttl_seconds: int = 600,      # 10 minutes — thread reposts are daily anyway
        max_comments: int = 500,           # a busy thread has ~500 top-level posts
    ):
        super().__init__(api_key=None, timeout=timeout)
        self.max_retries = max_retries
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_comments = max_comments
        self._client: Optional[httpx.AsyncClient] = None
        self._cached_posts: list[HNHiringPost] | None = None
        self._cache_time: Optional[datetime] = None

    # --- interface properties -------------------------------------------------

    @property
    def source_type(self) -> str:
        return self.SOURCE_TYPE

    @property
    def provider(self) -> str:
        return self.PROVIDER

    @property
    def role(self) -> ConnectorRole:
        return self.ROLE

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # --- HTTP helpers ----------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                headers={
                    "Accept": "application/json",
                    "User-Agent": "B2BLeadEngine/1.0 (+https://github.com/syedali254/RevOps; source=hacker-news)",
                },
            )
        return self._client

    async def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET with bounded retries. Raises only after the last attempt."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client()
                response = await client.get(f"{self.API_BASE}{path}", params=params)
                if response.status_code == 429:
                    await _sleep(2 ** attempt)
                    continue
                if response.status_code >= 500:
                    await _sleep(2 ** attempt)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await _sleep(2 ** attempt)
                continue
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await _sleep(2 ** attempt)
                continue
        raise RuntimeError(f"HN API request failed after {self.max_retries + 1} attempts: {last_error}")

    # --- thread discovery -------------------------------------------------------

    async def _find_latest_hiring_thread(self) -> Optional[dict[str, Any]]:
        """Find the most recent 'Ask HN: Who is hiring?' story."""
        import datetime as _dt

        # The thread is posted on the 1st of every month, so looking back 40
        # days is enough to always catch the newest one.
        since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=40)
        numeric = int(since.timestamp())

        data = await self._get_json(
            "/search_by_date",
            params={
                "query": "who is hiring",
                "tags": "story,ask_hn",
                "numericFilters": f"created_at_i>{numeric}",
                "hitsPerPage": 20,
            },
        )
        for hit in data.get("hits", []):
            title = (hit.get("title") or "").lower()
            if title.startswith("ask hn: who is hiring") and hit.get("objectID"):
                return hit
        return None

    # --- parsing ---------------------------------------------------------------

    @staticmethod
    def _strip_html(html_text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html_text or "")
        text = unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _extract_first_link(html_text: str) -> Optional[str]:
        """Return the first meaningful company link in a post.

        HN escapes `/` in hrefs as `&#x2F;` — unescape before parsing. Social/
        recruiting URLs (LinkedIn etc.) are skipped so a later real company
        link can be used. HN/Algolia internal links never count.
        """
        for match in re.finditer(r'href=["\']([^"\']+)["\']', html_text or ""):
            url = unescape(match.group(1)).strip()
            if not url.startswith("http"):
                continue
            host = urlparse(url).netloc.lower()
            host = host[4:] if host.startswith("www.") else host
            if not host or host in _NON_COMPANY_DOMAINS:
                continue
            return url
        return None

    @staticmethod
    def _extract_domain_from_text(plain_text: str) -> Optional[str]:
        """Many posts embed the company site as plain text (no anchor link).

        Scan stripped text for the first non-HN URL and return its host.
        """
        for match in re.finditer(r"https?://([A-Za-z0-9.-]+)", plain_text or ""):
            host = match.group(1).lower().rstrip(".,;:)")
            if host.startswith("www."):
                host = host[4:]
            if not host or host in _NON_COMPANY_DOMAINS:
                continue
            return host
        return None

    def _parse_post(self, comment: dict[str, Any]) -> Optional[HNHiringPost]:
        """Parse one top-level comment; returns None when it isn't a company post."""
        raw_text = comment.get("text") or ""
        if not raw_text:
            return None

        text = self._strip_html(raw_text)
        first_line = re.split(r"[\r\n]", text, maxsplit=1)[0].strip()

        segments = [seg.strip() for seg in first_line.split("|") if seg.strip()]
        if len(segments) < 2:
            # Non-standard posts ("we're hiring, email me") are not parseable
            return None

        # Some posts embed a bare URL as its own segment ("Name | https://site
        # | Location | Role"). A URL is not a location — strip those out and
        # use them as a domain hint when no plain link was found in the HTML.
        url_pattern = re.compile(r"^(?:https?://\S+|(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?)$", re.IGNORECASE)
        url_segments = [seg for seg in segments if url_pattern.match(seg)]
        if url_segments:
            segments = [seg for seg in segments if seg not in url_segments]

        company = segments[0]
        # Drop obvious non-company names
        if not company or len(company) > 80 or company.lower().startswith(("i ", "im ", "i'm ", "we ")):
            return None
        company = re.split(r"\s+\(?\s*https?://", company)[0].strip().strip("/(,")
        if not company:
            return None

        location = segments[1] if len(segments) > 1 else ""
        role = segments[2] if len(segments) > 2 else ""

        domain = None
        link = self._extract_first_link(raw_text)
        if link:
            host = urlparse(link).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            if host and host not in _NON_COMPANY_DOMAINS:
                domain = host or None
        if domain is None:
            domain = self._extract_domain_from_text(text)
        if domain is None and url_segments:
            # Fall back to the bare-URL segment itself ("example.com/careers").
            # urlparse needs a scheme to return a netloc — add one when missing,
            # and always re-check the final host against the blocklist.
            segment = url_segments[0].strip()
            candidate = segment if segment.startswith("http") else f"https://{segment}"
            host = urlparse(candidate).netloc.lower() or segment.split("/")[0].lower()
            if host.startswith("www."):
                host = host[4:]
            host = host.split("/")[0]
            if host and host not in _NON_COMPANY_DOMAINS:
                domain = host or None

        permalink = (
            f"https://news.ycombinator.com/item?id={comment.get('objectID') or comment.get('id') or ''}"
        )
        created_raw = comment.get("created_at")
        created_at: Optional[datetime] = None
        if created_raw:
            try:
                created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                created_at = None

        return HNHiringPost(
            hn_id=int(comment.get("objectID") or comment.get("id") or 0),
            company=company,
            location=location,
            role=role,
            domain=domain,
            text_url=permalink,
            snippet=text[:250],
            permalink=permalink,
            created_at=created_at,
        )

    async def _fetch_posts(self) -> list[HNHiringPost]:
        """Fetch the latest Who-is-Hiring thread and parse top-level posts (cached)."""
        now = datetime.now(timezone.utc)
        if (
            self._cached_posts is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < self.cache_ttl_seconds
        ):
            return self._cached_posts

        thread = await self._find_latest_hiring_thread()
        if thread is None:
            self._cached_posts = []
            self._cache_time = now
            return []

        item = await self._get_json(f"/items/{thread['objectID']}")
        posts: list[HNHiringPost] = []
        seen_ids: set[int] = set()
        for child in item.get("children", [])[: self.max_comments]:
            if not isinstance(child, dict):
                continue
            post = self._parse_post(child)
            if post is None:
                continue
            post_id = post.hn_id
            if post_id in seen_ids:
                continue
            if post_id != 0:
                seen_ids.add(post_id)
            posts.append(post)

        self._cached_posts = posts
        self._cache_time = now
        return posts

    # --- matching ---------------------------------------------------------------

    @staticmethod
    def _match_country(location: str, query_countries: list[str]) -> Optional[str]:
        """Return the matched campaign country name, or None (unknown)."""
        loc = f" {location.lower()} "
        for country in query_countries:
            aliases = _COUNTRY_ALIASES.get(country.lower(), {country.lower()})
            if any(alias in loc for alias in aliases):
                return country
        return None

    def _is_relevant(self, post: HNHiringPost, query: DiscoveryQuery) -> bool:
        """Sector/keyword filter: unknown never counts as a match."""
        sectors = [s.strip().lower() for s in query.sectors if s.strip()]
        if not sectors:
            return True
        haystack = f" {post.role} {post.company} {post.snippet} ".lower()
        return any(
            kw in haystack
            for kw in sectors + sorted(_SECTOR_KEYWORDS)
        )

    # --- connector interface ----------------------------------------------------

    async def discover(self, query: DiscoveryQuery) -> ConnectorResult:
        request_meta = {
            "query_countries": query.countries,
            "query_sectors": query.sectors,
            "max_results": query.max_results,
        }
        try:
            posts = await self._fetch_posts()
        except Exception as e:
            return self._make_result(
                status=ConnectorStatus.FAILED,
                candidates=[],
                error_code="fetch_failed",
                error_message=f"Failed to fetch Hacker News hiring thread: {e}",
                request_meta=request_meta,
            )

        candidates: list[CandidateCompany] = []
        skipped_country = 0
        skipped_irrelevant = 0

        for post in posts:
            if len(candidates) >= query.max_results:
                break

            if not self._is_relevant(post, query):
                skipped_irrelevant += 1
                continue

            country = self._match_country(post.location, [c for c in query.countries])
            if query.countries and country is None and post.location:
                loc_lower = f" {post.location.lower()} "
                if not any(token in loc_lower for token in ("remote", "worldwide", "anywhere")):
                    skipped_country += 1
                    continue  # clearly outside the target geography

            candidate = CandidateCompany(
                name=post.company,
                website_domain=post.domain,
                country=country,
                sector=self._sector_from_post(post),
                employee_min=None,           # honest: unknown
                employee_max=None,
                source_url=post.permalink,
                snippet=f"Hiring: {post.role or role_of(post)} — “{post.snippet}”",
                provider_meta={
                    "thread_comment_id": post.hn_id,
                    "location_raw": post.location,
                    "role_raw": post.role,
                    "posted_at": post.created_at.isoformat() if post.created_at else None,
                },
            )
            candidates.append(candidate)

        status = (
            ConnectorStatus.SUCCESS_WITH_RESULTS
            if candidates
            else ConnectorStatus.SUCCESS_EMPTY
        )
        meta = {
            **request_meta,
            "posts_parsed": len(posts),
            "returned": len(candidates),
            "skipped_outside_location": skipped_country,
            "skipped_not_relevant": skipped_irrelevant,
        }
        if posts and not candidates:
            meta["note"] = (
                "Thread parsed but no posts matched campaign criteria "
                "(country filter was applied)."
            )
        return self._make_result(status=status, candidates=candidates, request_meta=meta)

    def _sector_from_post(self, post: HNHiringPost) -> Optional[str]:
        role_lower = (post.role or "").lower()
        matched = [kw for kw in sorted(_SECTOR_KEYWORDS) if kw in role_lower]
        if matched:
            return ", ".join(matched[:3])
        return role_lower.split()[0].title() if role_lower else None

    async def enrich(self, company_ids: list[int], query: EnrichmentQuery) -> ConnectorResult:
        """HN is discovery-only; enrichment runs are reported as unsupported."""
        request_meta = {"company_ids": company_ids}
        try:
            posts = await self._fetch_posts()
        except Exception as e:
            return self._make_result(
                status=ConnectorStatus.FAILED,
                candidates=[],
                error_code="fetch_failed",
                error_message=f"Failed to fetch Hacker News hiring thread: {e}",
                request_meta=request_meta,
            )

        from ..models import Company
        from ..db import session_scope

        names: set[str] = set()
        domains: set[str] = set()
        with session_scope() as db:
            rows = db.query(Company).filter(Company.id.in_(company_ids)).all() if company_ids else []
            for c in rows:
                if c.canonical_name:
                    names.add(c.canonical_name.strip().lower())
                if c.website_domain:
                    domains.add(c.website_domain.strip().lower())

        matched = [
            p for p in posts
            if p.company.strip().lower() in names
            or (p.domain is not None and p.domain in domains)
        ]
        return self._make_result(
            status=ConnectorStatus.SUCCESS_WITH_RESULTS if matched else ConnectorStatus.SUCCESS_EMPTY,
            candidates=[],
            request_meta={
                "company_ids": company_ids,
                "hiring_posts_found": len(matched),
                "sample_roles": [m.role for m in matched[:5]],
                "comment_links": [m.permalink for m in matched[:5]],
            },
        )


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)


def role_of(post: HNHiringPost) -> str:
    """Fallback label when a post has no explicit role segment."""
    return "Hiring (role not specified)"


# Singleton
_hn_connector: Optional[HNHiringConnector] = None


def get_hn_connector() -> HNHiringConnector:
    global _hn_connector
    if _hn_connector is None:
        _hn_connector = HNHiringConnector()
    return _hn_connector
