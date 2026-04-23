"""
PROVCHAIN — Scan Route (Stub)
===============================
POST /scan/{asset_id} — triggers a propagation scan for a registered asset.
Implementation in Phase 3.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Monitoring"])


@router.post("/scan/{asset_id}")
async def trigger_scan(asset_id: str):
    """
    Trigger a propagation scan for a registered asset.

    Searches Google Custom Search, News API, and Wayback Machine
    for copies of the asset, then runs propagation analysis.

    **Status: Phase 3 — not yet implemented.**
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": f"Scan for asset '{asset_id}' — Phase 3 (coming soon)",
        },
    )
