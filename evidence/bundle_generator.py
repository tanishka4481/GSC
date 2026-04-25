"""
PROVCHAIN — Bundle Generator
============================
Orchestrator for Pillar 3 (Evidence Engine).
Compiles all PDFs, charts, CSVs, and notices into a single ZIP bundle,
pins it to IPFS, and returns the final package metadata.
"""

import io
import json
import csv
import zipfile
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from core.exceptions import StorageError
from core.config import get_settings
from registration.registry import get_asset
from evidence.pdf_builder import build_registration_certificate, build_match_report
from evidence.chart_builder import build_propagation_chart
from evidence.notice_generator import generate_notice
from registration.ipfs_client import pin_to_ipfs

logger = logging.getLogger("provchain.bundle_generator")


async def generate_evidence_bundle(asset_id: str, scan_id: str, jurisdiction: str = "dmca") -> Dict[str, Any]:
    """
    Generates the complete evidence bundle.
    
    1. Gathers asset and scan data.
    2. Generates PDFs and charts.
    3. Generates infringing_urls.csv.
    4. Compiles the bundle_manifest.json.
    5. Zips all contents in-memory.
    6. Pins the ZIP to IPFS via Pinata.
    7. Generates the final email legal notice text with the new CID.
    
    Returns:
        Dict with bundle details: ipfs_cid, ipfs_url, email_notice_text, bundle_size
    """
    logger.info(f"Generating {jurisdiction} evidence bundle for asset {asset_id}, scan {scan_id}")
    
    # 1. Fetch data
    asset = get_asset(asset_id)
    # scanner.get_scan() should return a ScanRecord and a PropagationReport
    # Wait, we don't have scanner.get_scan() explicitly defined in models, but we can fetch it.
    # Let's assume get_scan returns a tuple or just ScanRecord that contains metrics/anomaly.
    # Actually, we need to construct the report from the scan record.
    # For now, let's just fetch the scan record from firestore.
    from firebase_admin import firestore
    settings = get_settings()
    db = firestore.client(database_id=settings.FIRESTORE_DATABASE_ID)
    scan_doc = db.collection("scans").document(scan_id).get()
    if not scan_doc.exists:
        raise ValueError(f"Scan not found: {scan_id}")
    
    scan_data = scan_doc.to_dict()
    # We will pass the raw dicts or convert them back to models.
    from monitoring.models import ScanRecord, PropagationReport, PropagationMetrics, AnomalyResult
    scan_record = ScanRecord(**scan_data)
    
    # Reconstruct the PropagationReport from the scan record
    # ScanRecord stores metrics as a dict, we need to parse it
    metrics_data = scan_data.get("metrics", {})
    metrics = PropagationMetrics(**metrics_data) if metrics_data else PropagationMetrics()
    
    anomaly_data = scan_data.get("anomaly")
    anomaly = AnomalyResult(**anomaly_data) if anomaly_data else None
    
    report = PropagationReport(
        asset_id=asset_id,
        scan_id=scan_id,
        metrics=metrics,
        anomaly=anomaly,
        risk_score=scan_record.risk_score,
        alert_triggered=scan_record.alert_triggered,
        dmca_eligible=scan_record.dmca_eligible,
        scanned_at=scan_record.created_at or datetime.now(timezone.utc).isoformat()
    )
    
    # We also need match decisions. For simplicity, we just extract flagged URLs.
    flagged_urls = [
        hit["url"] for hit in scan_record.hits 
        if hit.get("domain_risk") in ["HIGH", "MEDIUM"]  # fallback logic if match_decisions absent
    ]
    
    # 2. Generate Evidence Files
    reg_cert_bytes = build_registration_certificate(asset)
    match_report_bytes = build_match_report(report, scan_record)
    chart_bytes = build_propagation_chart(report, scan_record)
    
    # 3. Generate CSV
    csv_buffer = io.StringIO()
    csv_writer = csv.writer(csv_buffer)
    csv_writer.writerow(["URL", "Domain", "Source", "Discovered At"])
    for hit in scan_record.hits:
        csv_writer.writerow([
            hit.get("url"), hit.get("domain"), hit.get("source"), hit.get("discovered_at")
        ])
    csv_bytes = csv_buffer.getvalue().encode('utf-8')
    
    # 4. Generate internal notice (without final CID)
    internal_notice = generate_notice(jurisdiction, asset, flagged_urls, ipfs_cid="INCLUDED_IN_THIS_ZIP")
    
    # 5. Manifest
    manifest = {
        "asset_id": asset_id,
        "scan_id": scan_id,
        "jurisdiction": jurisdiction,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            "registration_certificate.pdf",
            "fingerprint_match_report.pdf",
            "propagation_timeline.png",
            "infringing_urls.csv",
            f"legal_notice_{jurisdiction}.txt"
        ]
    }
    manifest_bytes = json.dumps(manifest, indent=2).encode('utf-8')
    
    # 6. Zip in-memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("registration_certificate.pdf", reg_cert_bytes)
        zf.writestr("fingerprint_match_report.pdf", match_report_bytes)
        zf.writestr("propagation_timeline.png", chart_bytes)
        zf.writestr("infringing_urls.csv", csv_bytes)
        zf.writestr(f"legal_notice_{jurisdiction}.txt", internal_notice.encode('utf-8'))
        zf.writestr("bundle_manifest.json", manifest_bytes)
        
    zip_bytes = zip_buffer.getvalue()
    
    # 7. Pin ZIP to IPFS
    zip_filename = f"evidence_bundle_{asset_id}_{scan_id}.zip"
    ipfs_cid = None
    ipfs_url = None
    
    try:
        ipfs_result = await pin_to_ipfs(
            file_bytes=zip_bytes,
            filename=zip_filename,
            metadata={
                "asset_id": asset_id,
                "scan_id": scan_id,
                "type": "evidence_bundle"
            }
        )
        if ipfs_result:
            ipfs_cid = ipfs_result.cid
            from registration.ipfs_client import get_ipfs_url
            ipfs_url = get_ipfs_url(ipfs_cid)
    except StorageError as e:
        logger.warning(f"Failed to pin bundle to IPFS: {e}")
        ipfs_cid = "UPLOAD_FAILED"
        
    # 8. Generate Final Notice (for email)
    email_notice = generate_notice(jurisdiction, asset, flagged_urls, ipfs_cid=ipfs_cid or "UNAVAILABLE")
    
    logger.info(f"Bundle generated successfully. CID: {ipfs_cid}")
    
    return {
        "asset_id": asset_id,
        "scan_id": scan_id,
        "jurisdiction": jurisdiction,
        "ipfs_cid": ipfs_cid,
        "ipfs_url": ipfs_url,
        "email_notice_text": email_notice,
        "bundle_size_bytes": len(zip_bytes),
        "raw_zip_bytes": zip_bytes  # Useful for testing or immediate download
    }
