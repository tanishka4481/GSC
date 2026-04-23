"""
PROVCHAIN — Alerts Route (Stub)
=================================
GET /alerts — returns propagation anomaly alerts.
Implementation in Phase 3.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Monitoring"])


@router.get("/alerts")
async def get_alerts():
    """
    Get propagation anomaly alerts for the authenticated publisher.

    Returns real-time alerts from Firebase RTDB when anomalies
    are confirmed by the propagation analyzer.

    **Status: Phase 3 — not yet implemented.**
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": "Alerts — Phase 3 (coming soon)",
        },
    )
