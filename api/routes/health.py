"""
PROVCHAIN — Health Check Route
================================
GET /health — returns server status, version, and timestamp.
No authentication required.
"""

from datetime import datetime, timezone

from fastapi import APIRouter

from core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns server status, app version, and current UTC timestamp.
    Used by Cloud Run health checks and monitoring.
    """
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
