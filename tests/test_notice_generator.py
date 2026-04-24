import pytest
from evidence.notice_generator import generate_notice
from registration.models import AssetRecord

def test_generate_notice_dmca():
    asset = AssetRecord(
        asset_id="test-asset-123",
        owner_id="user-1",
        filename="image.jpg",
        content_type="image/jpeg",
        file_size=1024,
        sha256="fakehash123",
        created_at="2026-04-24T12:00:00Z"
    )
    
    urls = ["https://baddomain.com/stolen.jpg", "https://scrapersite.org/img.jpg"]
    
    notice = generate_notice(
        jurisdiction="dmca",
        asset=asset,
        infringing_urls=urls,
        ipfs_cid="ipfs-cid-999"
    )
    
    assert "Notice of Copyright Infringement (DMCA)" in notice
    assert "test-asset-123" in notice
    assert "fakehash123" in notice
    assert "ipfs-cid-999" in notice
    assert "https://baddomain.com/stolen.jpg" in notice
    assert "https://scrapersite.org/img.jpg" in notice

def test_generate_notice_invalid_jurisdiction():
    asset = AssetRecord(
        asset_id="test-asset-123",
        owner_id="user-1",
        filename="image.jpg",
        content_type="image/jpeg",
        file_size=1024,
        sha256="fakehash123"
    )
    
    with pytest.raises(ValueError):
        generate_notice(
            jurisdiction="nonexistent",
            asset=asset,
            infringing_urls=["http://bad.com"],
            ipfs_cid="ipfs-cid-999"
        )
