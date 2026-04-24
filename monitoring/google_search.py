"""
PROVCHAIN — Google Custom Search API Client
=============================================
Low-level wrapper for Google Custom Search JSON API with daily quota tracking.

Free tier: 100 queries/day. Each scan uses 1-3 queries depending on asset type.
This module tracks daily usage and rejects requests that would exceed the quota.

Supports:
    - Web search (standard)
    - Image search (searchType=image)
    - News search (filtered web search with news-related params)
"""

import logging
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from core.config import get_settings
from core.exceptions import ScanError
from monitoring.models import SearchResult, ScanSource

logger = logging.getLogger("provchain.google_search")

# Google Custom Search API endpoint
CSE_API_URL = "https://www.googleapis.com/customsearch/v1"

# =============================================================================
# Daily Quota Tracker (in-memory, resets each day)
# =============================================================================

class _QuotaTracker:
    """
    Simple in-memory daily quota tracker.

    Tracks queries per calendar day (UTC). Resets automatically at midnight.
    For production, this should be backed by Firestore or Redis.
    """

    def __init__(self, daily_limit: int = 100):
        self.daily_limit = daily_limit
        self._count = 0
        self._date = date.today()

    def _maybe_reset(self) -> None:
        """Reset counter if we've crossed into a new day."""
        today = date.today()
        if today != self._date:
            logger.info("Quota reset: new day %s (previous: %s, used: %d)", today, self._date, self._count)
            self._count = 0
            self._date = today

    def can_query(self, n: int = 1) -> bool:
        """Check if we have enough quota for n queries."""
        self._maybe_reset()
        return (self._count + n) <= self.daily_limit

    def consume(self, n: int = 1) -> None:
        """Record n queries consumed."""
        self._maybe_reset()
        self._count += n
        logger.debug("Quota consumed: %d (total today: %d/%d)", n, self._count, self.daily_limit)

    @property
    def remaining(self) -> int:
        """Queries remaining today."""
        self._maybe_reset()
        return max(0, self.daily_limit - self._count)

    @property
    def used_today(self) -> int:
        """Queries used today."""
        self._maybe_reset()
        return self._count


# Global singleton tracker
_quota = _QuotaTracker(daily_limit=100)


def get_quota_status() -> Dict[str, Any]:
    """Return current quota status for API monitoring."""
    return {
        "daily_limit": _quota.daily_limit,
        "used_today": _quota.used_today,
        "remaining": _quota.remaining,
        "date": str(_quota._date),
    }


# =============================================================================
# Core Search Functions
# =============================================================================

async def search_web(
    query: str,
    num: int = 10,
) -> List[SearchResult]:
    """
    Perform a standard web search via Google Custom Search API.

    Args:
        query: Search query string.
        num: Number of results (1-10, CSE max per request).

    Returns:
        List of SearchResult objects.

    Raises:
        ScanError: If API key missing, quota exceeded, or API call fails.
    """
    return await _execute_search(
        query=query,
        num=num,
        search_type=None,
        source=ScanSource.GOOGLE_WEB,
    )


async def search_images(
    query: str,
    num: int = 10,
) -> List[SearchResult]:
    """
    Perform an image search via Google Custom Search API.

    Args:
        query: Search query string (typically the image filename or description).
        num: Number of results (1-10, CSE max per request).

    Returns:
        List of SearchResult objects with thumbnail_url populated.

    Raises:
        ScanError: If API key missing, quota exceeded, or API call fails.
    """
    return await _execute_search(
        query=query,
        num=num,
        search_type="image",
        source=ScanSource.GOOGLE_IMAGE,
    )


async def search_news(
    query: str,
    num: int = 10,
) -> List[SearchResult]:
    """
    Search for news articles via Google Custom Search API.

    Uses date-restricted search (last 30 days) and sorts by date
    to find recent news coverage of the content.

    Args:
        query: Search query string.
        num: Number of results (1-10).

    Returns:
        List of SearchResult objects from news sources.

    Raises:
        ScanError: If API key missing, quota exceeded, or API call fails.
    """
    return await _execute_search(
        query=query,
        num=num,
        search_type=None,
        source=ScanSource.GOOGLE_NEWS,
        extra_params={
            "sort": "date",          # Sort by date for recency
            "dateRestrict": "m1",    # Last 1 month
        },
    )


# =============================================================================
# Internal Implementation
# =============================================================================

async def _execute_search(
    query: str,
    num: int,
    search_type: Optional[str],
    source: ScanSource,
    extra_params: Optional[Dict[str, str]] = None,
) -> List[SearchResult]:
    """
    Execute a Google Custom Search API request.

    Args:
        query: Search query string.
        num: Number of results requested.
        search_type: 'image' for image search, None for web search.
        source: ScanSource enum for tagging results.
        extra_params: Additional API parameters.

    Returns:
        List of SearchResult objects.

    Raises:
        ScanError: On configuration, quota, or API errors.
    """
    settings = get_settings()

    # --- Validate configuration ---
    if not settings.CUSTOM_SEARCH_API_KEY:
        raise ScanError(
            message="Google Custom Search API key not configured",
            detail={"setting": "CUSTOM_SEARCH_API_KEY"},
        )
    if not settings.CUSTOM_SEARCH_CX:
        raise ScanError(
            message="Google Custom Search CX (engine ID) not configured",
            detail={"setting": "CUSTOM_SEARCH_CX"},
        )

    # --- Check quota ---
    if not _quota.can_query():
        raise ScanError(
            message=f"Google Custom Search daily quota exceeded ({_quota.daily_limit}/day)",
            detail=get_quota_status(),
        )

    # --- Build request params ---
    num = min(max(1, num), 10)  # CSE max is 10 per request
    params: Dict[str, Any] = {
        "key": settings.CUSTOM_SEARCH_API_KEY,
        "cx": settings.CUSTOM_SEARCH_CX,
        "q": query,
        "num": num,
    }

    if search_type:
        params["searchType"] = search_type

    if extra_params:
        params.update(extra_params)

    # --- Execute request ---
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(CSE_API_URL, params=params)
            _quota.consume(1)

            if response.status_code == 429:
                raise ScanError(
                    message="Google Custom Search API rate limit hit",
                    detail={"status_code": 429, "response": response.text[:200]},
                )

            if response.status_code != 200:
                raise ScanError(
                    message=f"Google Custom Search API error: HTTP {response.status_code}",
                    detail={
                        "status_code": response.status_code,
                        "response": response.text[:500],
                    },
                )

            data = response.json()

        # --- Parse results ---
        results = []
        items = data.get("items", [])

        for item in items:
            # Extract thumbnail for image search
            thumbnail = None
            if search_type == "image":
                image_info = item.get("image", {})
                thumbnail = image_info.get("thumbnailLink")
            elif item.get("pagemap", {}).get("cse_thumbnail"):
                thumbnails = item["pagemap"]["cse_thumbnail"]
                if thumbnails:
                    thumbnail = thumbnails[0].get("src")

            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                thumbnail_url=thumbnail,
                source=source,
                raw_metadata={
                    "displayLink": item.get("displayLink", ""),
                    "formattedUrl": item.get("formattedUrl", ""),
                    "mime": item.get("mime", ""),
                },
            ))

        logger.info(
            "Search complete: source=%s, query='%s…', results=%d, quota=%d/%d",
            source.value,
            query[:50],
            len(results),
            _quota.used_today,
            _quota.daily_limit,
        )

        return results

    except ScanError:
        raise
    except httpx.TimeoutException:
        raise ScanError(
            message="Google Custom Search API request timed out",
            detail={"query": query[:100], "timeout": 15.0},
        )
    except Exception as e:
        raise ScanError(
            message=f"Google Custom Search failed: {e}",
            detail={"query": query[:100]},
        )
