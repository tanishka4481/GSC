"""PROVCHAIN — Notice Route.

POST /notice/send
Generates a notice from evidence bundle data and optionally dispatches via Gmail.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import get_settings
from evidence.bundle_generator import generate_evidence_bundle
from evidence.gmail_sender import send_notice_email
from monitoring.propagation_analyzer import get_scan_history

router = APIRouter(tags=["Evidence"])


class NoticeSendRequest(BaseModel):
    asset_id: str = Field(..., description="Asset ID for which notice is generated")
    scan_id: Optional[str] = Field(default=None, description="Optional scan ID; defaults to latest")
    jurisdiction: str = Field(default="dmca", description="dmca | it_rules | copyright_act")
    to_email: Optional[str] = Field(default=None, description="Target abuse/legal email")


@router.post("/notice/send")
async def send_notice(payload: NoticeSendRequest):
    """Generate notice text and optionally dispatch via Gmail API."""
    try:
        settings = get_settings()

        scans = get_scan_history(payload.asset_id)
        if not scans:
            raise HTTPException(status_code=404, detail="No scan history found for this asset")

        selected_scan = scans[0]
        if payload.scan_id:
            matched = [scan for scan in scans if scan.scan_id == payload.scan_id]
            if not matched:
                raise HTTPException(status_code=404, detail=f"Scan not found: {payload.scan_id}")
            selected_scan = matched[0]

        if payload.jurisdiction == "dmca" and not selected_scan.dmca_eligible:
            raise HTTPException(
                status_code=400,
                detail="DMCA notice requires HIGH_CONFIDENCE match and minimum 2 independent URLs",
            )

        bundle = await generate_evidence_bundle(
            asset_id=payload.asset_id,
            scan_id=selected_scan.scan_id,
            jurisdiction=payload.jurisdiction,
        )

        recipient = payload.to_email
        if not recipient:
            return {
                "status": "preview_only",
                "dispatched": False,
                "message": "Notice generated. Provide 'to_email' to dispatch via Gmail.",
                "asset_id": payload.asset_id,
                "scan_id": selected_scan.scan_id,
                "jurisdiction": payload.jurisdiction,
                "ipfs_cid": bundle.get("ipfs_cid"),
                "notice_text": bundle.get("email_notice_text"),
            }

        subject = f"PROVCHAIN {payload.jurisdiction.upper()} Takedown Notice — Asset {payload.asset_id}"
        dispatched = send_notice_email(
            to_email=recipient,
            subject=subject,
            body=bundle.get("email_notice_text", ""),
        )

        if not dispatched:
            raise HTTPException(
                status_code=502,
                detail=(
                    "Notice generated but email dispatch failed. "
                    f"Check Gmail credentials/token paths: {settings.GMAIL_CREDENTIALS_PATH}, {settings.GMAIL_TOKEN_PATH}"
                ),
            )

        return {
            "status": "sent",
            "dispatched": True,
            "message": f"Notice sent to {recipient}",
            "asset_id": payload.asset_id,
            "scan_id": selected_scan.scan_id,
            "jurisdiction": payload.jurisdiction,
            "recipient": recipient,
            "ipfs_cid": bundle.get("ipfs_cid"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notice generation failed: {str(e)}")
