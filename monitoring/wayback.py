"""
PROVCHAIN — Wayback Machine CDX API Client
============================================
Query the Wayback Machine (Internet Archive) for archived snapshots of URLs.

This provides evidence of content existence at specific points in time,
which is valuable for:
    - Proving prior art (our content existed before the copy)
    - Capturing evidence of infringing pages (archived copies)
    - Establishing timeline of content propagation

The CDX API is free, requires no API key, and has generous rate limits.
Docs: https://github.com/internetarchive/wayback/tree/master/wayback-cdx-server
"""

import logging
from typing import List, Optional

import httpx

from core.exceptions import ScanError
from monitoring.models import WaybackSnapshot

logger = logging.getLogger("provchain.wayback")

# Wayback Machine CDX API endpoint
CDX_API_URL = "https://web.archive.org/cdx/search/cdx"

# Wayback Machine availability API (simpler, for quick checks)
AVAILABILITY_API_URL = "https://archive.org/wayback/available"


# =============================================================================
# Public API
# =============================================================================

async def check_availability(url: str) -> Optional[WaybackSnapshot]:
    """
    Quick check if a URL has ANY Wayback Machine snapshot.

    Uses the Availability API for fast lookups. Returns the closest
    snapshot if available, None otherwise.

    Args:
        url: URL to check for archived copies.

    Returns:
        WaybackSnapshot if archived, None if not.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                AVAILABILITY_API_URL,
                params={"url": url},
            )

            if response.status_code != 200:
                logger.warning("Wayback availability check failed: HTTP %d", response.status_code)
                return None

            data = response.json()
            snapshot_data = data.get("archived_snapshots", {}).get("closest")

            if not snapshot_data or not snapshot_data.get("available"):
                return None

            return WaybackSnapshot(
                url=url,
                archive_url=snapshot_data.get("url", ""),
                timestamp=snapshot_data.get("timestamp", ""),
                status_code=str(snapshot_data.get("status", "200")),
            )

    except httpx.TimeoutException:
        logger.warning("Wayback availability check timed out for: %s", url)
        return None
    except Exception as e:
        logger.warning("Wayback availability check error: %s", e)
        return None


async def get_snapshots(
    url: str,
    limit: int = 20,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> List[WaybackSnapshot]:
    """
    Get all archived snapshots of a URL from the Wayback Machine CDX API.

    Args:
        url: URL to search for snapshots.
        limit: Maximum number of snapshots to return.
        from_date: Start date filter (YYYYMMDD format).
        to_date: End date filter (YYYYMMDD format).

    Returns:
        List of WaybackSnapshot objects, ordered by timestamp (newest first).
    """
    try:
        params = {
            "url": url,
            "output": "json",
            "limit": str(limit),
            "fl": "timestamp,original,statuscode,mimetype",
            "sort": "reverse",  # Newest first
        }

        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(CDX_API_URL, params=params)

            if response.status_code != 200:
                logger.warning(
                    "Wayback CDX query failed: HTTP %d for %s",
                    response.status_code, url,
                )
                return []

            data = response.json()

            # CDX API returns array of arrays; first row is headers
            if not data or len(data) < 2:
                return []

            snapshots = []
            # Skip header row (index 0)
            for row in data[1:]:
                if len(row) >= 4:
                    timestamp, original, status, mime = row[0], row[1], row[2], row[3]
                    archive_url = f"https://web.archive.org/web/{timestamp}/{original}"
                    snapshots.append(WaybackSnapshot(
                        url=original,
                        archive_url=archive_url,
                        timestamp=timestamp,
                        status_code=status,
                        mime_type=mime,
                    ))

            logger.info("Wayback snapshots found: %d for %s", len(snapshots), url)
            return snapshots

    except httpx.TimeoutException:
        logger.warning("Wayback CDX query timed out for: %s", url)
        return []
    except Exception as e:
        logger.warning("Wayback CDX query error for %s: %s", url, e)
        return []


async def get_earliest_snapshot(url: str) -> Optional[WaybackSnapshot]:
    """
    Get the earliest archived snapshot of a URL.

    Useful for establishing when content first appeared at a URL,
    which helps prove timeline in copyright disputes.

    Args:
        url: URL to check.

    Returns:
        Earliest WaybackSnapshot, or None if no snapshots exist.
    """
    try:
        params = {
            "url": url,
            "output": "json",
            "limit": "1",
            "fl": "timestamp,original,statuscode,mimetype",
            "sort": "default",  # Oldest first
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(CDX_API_URL, params=params)

            if response.status_code != 200:
                return None

            data = response.json()
            if not data or len(data) < 2:
                return None

            row = data[1]  # First result after header
            if len(row) >= 4:
                timestamp, original, status, mime = row[0], row[1], row[2], row[3]
                archive_url = f"https://web.archive.org/web/{timestamp}/{original}"
                return WaybackSnapshot(
                    url=original,
                    archive_url=archive_url,
                    timestamp=timestamp,
                    status_code=status,
                    mime_type=mime,
                )

            return None

    except Exception as e:
        logger.warning("Wayback earliest snapshot check error for %s: %s", url, e)
        return None


async def search_domain_snapshots(
    domain: str,
    match_type: str = "domain",
    limit: int = 50,
) -> List[WaybackSnapshot]:
    """
    Search for all archived pages under a domain.

    Useful for finding all archived copies of content across a domain
    that may be hosting unauthorized copies.

    Args:
        domain: Domain to search (e.g., 'example.com').
        match_type: CDX match type — 'domain', 'host', 'prefix', or 'exact'.
        limit: Maximum results.

    Returns:
        List of WaybackSnapshot objects.
    """
    try:
        params = {
            "url": domain,
            "output": "json",
            "limit": str(limit),
            "fl": "timestamp,original,statuscode,mimetype",
            "matchType": match_type,
            "filter": "statuscode:200",  # Only successful captures
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(CDX_API_URL, params=params)

            if response.status_code != 200:
                return []

            data = response.json()
            if not data or len(data) < 2:
                return []

            snapshots = []
            for row in data[1:]:
                if len(row) >= 4:
                    timestamp, original, status, mime = row[0], row[1], row[2], row[3]
                    archive_url = f"https://web.archive.org/web/{timestamp}/{original}"
                    snapshots.append(WaybackSnapshot(
                        url=original,
                        archive_url=archive_url,
                        timestamp=timestamp,
                        status_code=status,
                        mime_type=mime,
                    ))

            logger.info(
                "Wayback domain search: %d snapshots for %s",
                len(snapshots), domain,
            )
            return snapshots

    except Exception as e:
        logger.warning("Wayback domain search error for %s: %s", domain, e)
        return []
