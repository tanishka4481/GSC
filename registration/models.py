"""
PROVCHAIN — Registration Data Models
======================================
Pydantic models for the entire registration pipeline.
Each module produces a typed output; registry.py composes them all.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Hasher Output
# =============================================================================

class AssetHash(BaseModel):
    """Output of hasher.hash_asset()."""
    sha256: str = Field(..., description="SHA-256 hex digest of the (normalized) file")
    normalized_bytes: bytes = Field(..., description="File bytes after normalization", exclude=True)
    content_type: str = Field(..., description="MIME type of the uploaded file")
    file_size: int = Field(..., description="Size of the original file in bytes")


# =============================================================================
# Fingerprint Output
# =============================================================================

class AssetFingerprint(BaseModel):
    """Output of fingerprint.generate_fingerprints()."""
    phash: Optional[str] = Field(None, description="Perceptual hash hex string (images only)")
    embedding: Optional[List[float]] = Field(None, description="Gemini embedding vector")
    embedding_model: Optional[str] = Field(None, description="Model used for embedding")
    content_summary: Optional[str] = Field(None, description="Short content-derived search summary")


# =============================================================================
# Timestamp Output
# =============================================================================

class TimestampProof(BaseModel):
    """Output of timestamp.create_timestamp()."""
    status: str = Field(..., description="pending | confirmed | unverified")
    ots_proof: Optional[str] = Field(None, description="Base64-encoded .ots proof bytes")
    submitted_at: str = Field(..., description="ISO 8601 UTC timestamp when submitted")
    confirmed_at: Optional[str] = Field(None, description="ISO 8601 UTC when Bitcoin-confirmed")
    bitcoin_block: Optional[int] = Field(None, description="Bitcoin block height (when confirmed)")


# =============================================================================
# IPFS Output
# =============================================================================

class IPFSResult(BaseModel):
    """Output of ipfs_client.pin_to_ipfs()."""
    cid: str = Field(..., description="IPFS content identifier (CID)")
    pin_size: int = Field(..., description="Size of pinned content in bytes")
    timestamp: str = Field(..., description="ISO 8601 UTC when pinned")


# =============================================================================
# Full Asset Record (Firestore document)
# =============================================================================

class AssetRecord(BaseModel):
    """Complete asset record stored in Firestore 'assets' collection."""
    asset_id: str
    owner_id: str
    filename: str
    content_type: str
    file_size: int
    sha256: str
    phash: Optional[str] = None
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    content_summary: Optional[str] = None
    ipfs_cid: Optional[str] = None
    ipfs_url: Optional[str] = None
    timestamp_proof: Optional[Dict[str, Any]] = None
    status: str = "registered"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to dict suitable for Firestore .set()."""
        data = self.model_dump(exclude_none=False)
        # Remove the raw embedding from the serialized form if it's too large
        # (Firestore has a 1MB document limit)
        return data


# =============================================================================
# API Response
# =============================================================================

class RegisterResponse(BaseModel):
    """Response returned by POST /register."""
    asset_id: str
    sha256: str
    phash: Optional[str] = None
    embedding_model: Optional[str] = None
    ipfs_cid: Optional[str] = None
    ipfs_url: Optional[str] = None
    timestamp_status: Optional[str] = None
    status: str
    created_at: Optional[str] = None


# =============================================================================
# Constants
# =============================================================================

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
}

SUPPORTED_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/html",
    "text/csv",
    "application/pdf",
}

SUPPORTED_CONTENT_TYPES = SUPPORTED_IMAGE_TYPES | SUPPORTED_TEXT_TYPES
