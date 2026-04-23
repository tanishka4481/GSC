"""
PROVCHAIN — Rate Limiter Middleware
=====================================
Simple in-memory sliding window rate limiter.

Tracks requests per client IP within a configurable time window.
Raises RateLimitError when the limit is exceeded.

Note: This is an in-memory implementation suitable for single-instance
deployments. For multi-instance Cloud Run, switch to Redis-backed
rate limiting.
"""

import logging
import time
from collections import defaultdict
from typing import List, Tuple

from fastapi import Request

from core.config import get_settings
from core.exceptions import RateLimitError

logger = logging.getLogger(__name__)

# In-memory store: {client_ip: [(timestamp, ...), ...]}
_request_log: dict[str, List[float]] = defaultdict(list)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For behind Cloud Run."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _cleanup_old_entries(entries: List[float], window: int) -> List[float]:
    """Remove entries older than the time window."""
    cutoff = time.time() - window
    return [t for t in entries if t > cutoff]


async def check_rate_limit(request: Request) -> None:
    """
    Check if the client has exceeded the rate limit.

    Call this as a dependency in routes that need rate limiting:

        @router.post("/register")
        async def register(_, _rl=Depends(check_rate_limit)):
            ...

    Raises:
        RateLimitError: if the client has exceeded the configured limit.
    """
    settings = get_settings()
    client_ip = _get_client_ip(request)

    # Clean up old entries
    _request_log[client_ip] = _cleanup_old_entries(
        _request_log[client_ip],
        settings.RATE_LIMIT_WINDOW_SECONDS,
    )

    # Check limit
    if len(_request_log[client_ip]) >= settings.RATE_LIMIT_REQUESTS:
        logger.warning(
            f"Rate limit exceeded for {client_ip}: "
            f"{len(_request_log[client_ip])} requests in "
            f"{settings.RATE_LIMIT_WINDOW_SECONDS}s"
        )
        raise RateLimitError(
            message="Too many requests — please try again later",
            detail={
                "limit": settings.RATE_LIMIT_REQUESTS,
                "window_seconds": settings.RATE_LIMIT_WINDOW_SECONDS,
            },
        )

    # Record this request
    _request_log[client_ip].append(time.time())
