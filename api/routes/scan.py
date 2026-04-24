"""
PROVCHAIN — Scan Routes
=========================
POST /scan/{asset_id} — Trigger a propagation scan
GET  /scan/{asset_id}/history — Get scan history
"""

from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.exceptions import ScanError, StorageError
from monitoring.scanner import scan_asset
from monitoring.propagation_analyzer import analyze_propagation, get_scan_history
from monitoring.domain_scorer import score_domains_batch
from monitoring.anomaly_detector import classify_anomaly
from monitoring.models import ScanResponse, ScanRecord

router = APIRouter(tags=["Monitoring"])


@router.post("/scan/{asset_id}", response_model=ScanResponse)
async def trigger_scan(asset_id: str):
    """
    Trigger a full propagation scan for a registered asset.
    
    1. Orchestrates Google searches + Wayback lookups.
    2. Downloads and fingerprints candidates (pHash / embedding).
    3. Scores domains for risk context.
    4. Computes match decisions and propagation metrics.
    5. Detects anomalies and persists results.
    """
    try:
        # Step 1: Scan
        scan_record, scan_hits, asset = await scan_asset(asset_id)

        # Step 2: Score domains
        domains = [hit.domain for hit in scan_hits]
        domain_scores = score_domains_batch(domains)

        # Step 3: Analyze
        report = await analyze_propagation(
            asset_id=asset_id,
            scan_hits=scan_hits,
            asset=asset,
            domain_scores=domain_scores,
            scan_record=scan_record,
        )

        # Step 4: Detect anomalies
        anomaly = classify_anomaly(report.metrics, report.match_decisions)
        
        # We also want to update the scan record with the anomaly
        scan_record.anomaly = anomaly.model_dump()
        from monitoring.propagation_analyzer import _save_scan_record
        await _save_scan_record(scan_record)

        # Build response
        high_conf = sum(1 for d in report.match_decisions if d.confidence == "HIGH_CONFIDENCE")
        probable = sum(1 for d in report.match_decisions if d.confidence == "PROBABLE_MATCH")
        possible = sum(1 for d in report.match_decisions if d.confidence == "POSSIBLE_MATCH")

        # Zip hits and decisions for the response
        hits_data = []
        for hit, decision in zip(scan_hits, report.match_decisions):
            hit_dict = hit.model_dump()
            hit_dict["decision"] = decision.model_dump()
            hits_data.append(hit_dict)

        return ScanResponse(
            scan_id=scan_record.scan_id,
            asset_id=asset_id,
            total_hits=len(scan_hits),
            high_confidence=high_conf,
            probable_match=probable,
            possible_match=possible,
            risk_score=report.risk_score,
            anomaly_type=anomaly.anomaly_type.value,
            alert_triggered=report.alert_triggered,
            dmca_eligible=report.dmca_eligible,
            hits=hits_data,
            scanned_at=report.scanned_at,
        )

    except ScanError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/scan/{asset_id}/history", response_model=List[ScanRecord])
async def list_scan_history(asset_id: str):
    """Get scan history for an asset."""
    try:
        records = get_scan_history(asset_id)
        return records
    except StorageError as e:
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
