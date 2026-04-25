"""
PROVCHAIN — SerpApi Search Client
==================================
Low-level wrapper for SerpApi with lightweight usage tracking.

Supports:
    - Web search (Google engine)
    - Image search (Google Images engine)
    - News search (Google News engine)
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import httpx

from core.config import get_settings
from core.exceptions import ScanError
from monitoring.models import SearchResult, ScanSource

logger = logging.getLogger("provchain.search")

SERPAPI_URL = "https://serpapi.com/search.json"


class _QuotaTracker:
    """Simple in-memory daily query tracker."""

    def __init__(self, daily_limit: int = 100):
        self.daily_limit = daily_limit
        self._count = 0
        self._date = date.today()

    def _maybe_reset(self) -> None:
        today = date.today()
        if today != self._date:
            logger.info("Quota reset: new day %s (previous: %s, used: %d)", today, self._date, self._count)
            self._count = 0
            self._date = today

    def can_query(self, n: int = 1) -> bool:
        self._maybe_reset()
        return (self._count + n) <= self.daily_limit

    def consume(self, n: int = 1) -> None:
        self._maybe_reset()
        self._count += n

    @property
    def remaining(self) -> int:
        self._maybe_reset()
        return max(0, self.daily_limit - self._count)

    @property
    def used_today(self) -> int:
        self._maybe_reset()
        return self._count


_quota = _QuotaTracker(daily_limit=100)


def get_quota_status() -> Dict[str, Any]:
    return {
        "daily_limit": _quota.daily_limit,
        "used_today": _quota.used_today,
        "remaining": _quota.remaining,
        "date": str(_quota._date),
    }


async def search_web(query: str, num: int = 10) -> List[SearchResult]:
    return await _execute_search(query=query, num=num, engine="google", source=ScanSource.GOOGLE_WEB)


async def search_images(query: str, num: int = 10) -> List[SearchResult]:
    return await _execute_search(query=query, num=num, engine="google_images", source=ScanSource.GOOGLE_IMAGE)


async def search_news(query: str, num: int = 10) -> List[SearchResult]:
    return await _execute_search(query=query, num=num, engine="google_news", source=ScanSource.GOOGLE_NEWS)


async def _execute_search(
    query: str,
    num: int,
    engine: str,
    source: ScanSource,
) -> List[SearchResult]:
    settings = get_settings()

    if not settings.SERPAPI_API_KEY:
        raise ScanError(
            message="SerpApi API key not configured",
            detail={"setting": "SERPAPI_API_KEY"},
        )

    if not _quota.can_query():
        raise ScanError(
            message=f"SerpApi daily quota exceeded ({_quota.daily_limit}/day)",
            detail=get_quota_status(),
        )

    num = min(max(1, num), 10)
    params: Dict[str, Any] = {
        "engine": engine,
        "q": query,
        "api_key": settings.SERPAPI_API_KEY,
        "num": num,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(SERPAPI_URL, params=params)
            _quota.consume(1)

            if response.status_code != 200:
                raise ScanError(
                    message=f"SerpApi error: HTTP {response.status_code}",
                    detail={"status_code": response.status_code, "response": response.text[:500]},
                )

            data = response.json()

        results: List[SearchResult] = []

        if engine == "google_images":
            items = data.get("images_results", [])
            for item in items:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        thumbnail_url=item.get("thumbnail"),
                        source=source,
                        raw_metadata={
                            "source": item.get("source", ""),
                            "original": item.get("original", ""),
                            "position": item.get("position", 0),
                        },
                    )
                )
        else:
            key = "news_results" if engine == "google_news" else "organic_results"
            items = data.get(key, [])
            for item in items:
                thumbnail = None
                if item.get("thumbnail"):
                    thumbnail = item.get("thumbnail")
                elif item.get("sitelinks") and isinstance(item["sitelinks"], list):
                    thumbnail = None

                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                        thumbnail_url=thumbnail,
                        source=source,
                        raw_metadata={
                            "displayed_link": item.get("displayed_link", ""),
                            "position": item.get("position", 0),
                            "date": item.get("date", ""),
                        },
                    )
                )

        logger.info(
            "Search complete: engine=%s, query='%s…', results=%d, quota=%d/%d",
            engine,
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
            message="SerpApi request timed out",
            detail={"query": query[:100], "timeout": 20.0},
        )
    except Exception as e:
        raise ScanError(
            message=f"SerpApi search failed: {e}",
            detail={"query": query[:100]},
        )
