import pytest
import io
import zipfile
from evidence.bundle_generator import generate_evidence_bundle
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
@patch('evidence.bundle_generator.get_asset')
@patch('evidence.bundle_generator.pin_to_ipfs')
@patch('firebase_admin.firestore.client')
async def test_generate_evidence_bundle(mock_db_client, mock_pin_to_ipfs, mock_get_asset):
    # Setup mocks
    from registration.models import AssetRecord
    mock_asset = AssetRecord(
        asset_id="asset-1",
        owner_id="owner-1",
        filename="test.jpg",
        content_type="image/jpeg",
        file_size=5000,
        sha256="hashhashhash",
        created_at="2026-04-24T00:00:00Z"
    )
    mock_get_asset.return_value = mock_asset
    
    mock_pin_result = MagicMock()
    mock_pin_result.cid = "mock-cid-456"
    mock_pin_to_ipfs.return_value = mock_pin_result
    
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "scan_id": "scan-1",
        "asset_id": "asset-1",
        "owner_id": "owner-1",
        "hits": [
            {
                "url": "http://bad.com/1",
                "domain": "bad.com",
                "source": "google_web",
                "discovered_at": "2026-04-24T01:00:00Z",
                "domain_risk": "HIGH"
            }
        ],
        "metrics": {
            "velocity": 1.0,
            "entropy": 0.0,
            "attribution_gap": 1.0,
            "total_hits": 1,
            "unique_domains": 1,
            "domain_risk_distribution": {"HIGH": 1},
            "temporal_spread_hours": 0.0
        },
        "risk_score": 0.9,
        "alert_triggered": True,
        "dmca_eligible": True,
        "status": "completed",
        "created_at": "2026-04-24T01:05:00Z"
    }
    
    mock_db = MagicMock()
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc
    mock_db_client.return_value = mock_db
    
    # Run the generator
    result = await generate_evidence_bundle("asset-1", "scan-1", "dmca")
    
    # Assertions
    assert result["asset_id"] == "asset-1"
    assert result["scan_id"] == "scan-1"
    assert result["ipfs_cid"] == "mock-cid-456"
    assert "mock-cid-456" in result["email_notice_text"]
    assert "http://bad.com/1" in result["email_notice_text"]
    
    # Verify ZIP contents
    zip_bytes = result["raw_zip_bytes"]
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert "registration_certificate.pdf" in namelist
        assert "fingerprint_match_report.pdf" in namelist
        assert "propagation_timeline.png" in namelist
        assert "infringing_urls.csv" in namelist
        assert "legal_notice_dmca.txt" in namelist
        assert "bundle_manifest.json" in namelist
        
        # Check CSV content
        csv_content = zf.read("infringing_urls.csv").decode("utf-8")
        assert "http://bad.com/1" in csv_content
        assert "bad.com" in csv_content
