"""PROVCHAIN — Evidence Route.

GET /evidence/{asset_id}
Generates an evidence bundle for an asset using the latest or specified scan.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from evidence.bundle_generator import generate_evidence_bundle
from monitoring.propagation_analyzer import get_scan_history

router = APIRouter(tags=["Evidence"])


@router.get("/evidence/{asset_id}")
async def get_evidence(
    asset_id: str,
    scan_id: str | None = Query(default=None, description="Optional scan ID; defaults to latest scan"),
    jurisdiction: str = Query(default="dmca", description="Notice template jurisdiction"),
    download: bool = Query(default=False, description="Return the generated ZIP as attachment"),
):
    """Generate and return evidence bundle metadata or ZIP download."""
    try:
        scans = get_scan_history(asset_id)
        if not scans:
            raise HTTPException(status_code=404, detail="No scan history found for this asset")

        selected_scan = scans[0]
        if scan_id:
            matched = [scan for scan in scans if scan.scan_id == scan_id]
            if not matched:
                raise HTTPException(status_code=404, detail=f"Scan not found: {scan_id}")
            selected_scan = matched[0]

        bundle = await generate_evidence_bundle(
            asset_id=asset_id,
            scan_id=selected_scan.scan_id,
            jurisdiction=jurisdiction,
        )

        if download:
            zip_bytes = bundle.get("raw_zip_bytes")
            if not zip_bytes:
                raise HTTPException(status_code=500, detail="Bundle generation failed to produce ZIP bytes")

            filename = f"evidence_bundle_{asset_id}_{selected_scan.scan_id}.zip"
            headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
            return StreamingResponse(
                content=iter([zip_bytes]),
                media_type="application/zip",
                headers=headers,
            )

        return {
            "asset_id": bundle.get("asset_id"),
            "scan_id": bundle.get("scan_id"),
            "jurisdiction": bundle.get("jurisdiction"),
            "ipfs_cid": bundle.get("ipfs_cid"),
            "ipfs_url": bundle.get("ipfs_url"),
            "bundle_size_bytes": bundle.get("bundle_size_bytes"),
            "message": "Evidence bundle generated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evidence generation failed: {str(e)}")
