"""
PROVCHAIN — Notice Route (Stub)
==================================
POST /notice/send — sends a legal notice (DMCA / IT Rules 2021).
Implementation in Phase 4.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["Evidence"])


@router.post("/notice/send")
async def send_notice():
    """
    Send a legal notice to the platform hosting infringing content.

    Requires HIGH_CONFIDENCE match + minimum 2 independent URLs.
    Dispatches via Gmail API and logs to Firestore.

    **Status: Phase 4 — not yet implemented.**
    """
    return JSONResponse(
        status_code=501,
        content={
            "error": "NotImplemented",
            "message": "Notice dispatch — Phase 4 (coming soon)",
        },
    )
