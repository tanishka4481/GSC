"""
PROVCHAIN — Evidence Route (Stub)
====================================
GET /evidence/{asset_id} — returns the evidence bundle for an asset.
Implementation in Phase 4.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Evidence"])


@router.get("/evidence/{asset_id}")
async def get_evidence(asset_id: str):
    """
    Get the evidence bundle for a registered asset.

    Returns the complete evidence package including registration
    certificate, fingerprint match report, propagation timeline,
    and legal notice — all pinned to IPFS.

    **Status: Phase 4 — not yet implemented.**
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": f"Evidence for asset '{asset_id}' — Phase 4 (coming soon)",
        },
    )
