"""
PROVCHAIN — Asset Registration Route (Stub)
=============================================
POST /register — registers a digital asset.
Implementation in Phase 2.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Registration"])


@router.post("/register")
async def register_asset():
    """
    Register a digital asset.

    Computes pHash + Gemini embedding + SHA-256, anchors timestamp,
    and stores in Firestore.

    **Status: Phase 2 — not yet implemented.**
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": "Asset registration — Phase 2 (coming soon)",
        },
    )
