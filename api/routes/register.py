"""
PROVCHAIN — Asset Registration Route
======================================
POST /register — registers a digital asset through the full pipeline:
Hash → Fingerprint (pHash + Gemini) → Timestamp (Bitcoin) → IPFS → Firestore
"""

import logging

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse

from core.config import get_settings
from core.exceptions import RegistrationError, StorageError
from registration.models import RegisterResponse, SUPPORTED_CONTENT_TYPES
from registration.registry import get_asset as _get_asset
from registration.registry import get_assets_by_owner as _get_assets_by_owner
from registration.registry import register_asset as _register_asset

logger = logging.getLogger("provchain.routes.register")

router = APIRouter(tags=["Registration"])


@router.get("/assets")
async def get_assets(
    owner_id: str = Query(..., description="Owner identifier (Firebase UID or demo-user)"),
):
    """List assets for a specific owner."""
    try:
        assets = _get_assets_by_owner(owner_id)
        return [asset.model_dump() for asset in assets]
    except StorageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/assets/{asset_id}")
async def get_asset(asset_id: str):
    """Fetch asset metadata for a specific asset ID."""
    try:
        asset = _get_asset(asset_id)
        return asset.model_dump()
    except RegistrationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except StorageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/register", response_model=RegisterResponse)
async def register_asset(
    file: UploadFile = File(
        ...,
        description="The digital asset file to register (image or text)",
    ),
    owner_id: str = Form(
        default="anonymous",
        description="Owner identifier (Firebase UID or 'anonymous')",
    ),
):
    """
    Register a digital asset.

    Processes the uploaded file through the full PROVCHAIN pipeline:

    1. **Hash** — SHA-256 with content normalization (images: strip EXIF, resize;
       text: normalize line endings)
    2. **Fingerprint** — Perceptual hash (images only) + Gemini semantic embedding
    3. **Timestamp** — Anchors the hash to the Bitcoin blockchain via OpenTimestamps
    4. **IPFS** — Pins the original file to IPFS via Pinata for tamper-proof archival
    5. **Store** — Writes the complete asset record to Firestore

    **Supported file types:**
    - Images: JPEG, PNG, WebP, GIF, BMP, TIFF
    - Text: Plain text, Markdown, HTML, CSV
    - Documents: PDF

    **Max file size:** Configured via MAX_UPLOAD_SIZE_MB (default: 100 MB)

    Returns the asset ID, SHA-256 digest, perceptual hash, IPFS CID,
    timestamp status, and registration status.
    """
    settings = get_settings()

    # --- Validate content type ---
    content_type = file.content_type or "application/octet-stream"
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise RegistrationError(
            message=f"Unsupported file type: {content_type}",
            detail={
                "content_type": content_type,
                "supported": sorted(SUPPORTED_CONTENT_TYPES),
            },
        )

    # --- Read file bytes ---
    file_bytes = await file.read()

    # --- Validate file size ---
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise RegistrationError(
            message=f"File too large: {len(file_bytes)} bytes exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit",
            detail={
                "file_size": len(file_bytes),
                "max_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            },
        )

    filename = file.filename or "unnamed"

    logger.info(
        "Registration request: file=%s, type=%s, size=%d, owner=%s",
        filename,
        content_type,
        len(file_bytes),
        owner_id,
    )

    # --- Run the full registration pipeline ---
    record = await _register_asset(
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
        owner_id=owner_id,
    )

    # --- Build response ---
    timestamp_status = None
    if record.timestamp_proof:
        timestamp_status = record.timestamp_proof.get("status")

    return RegisterResponse(
        asset_id=record.asset_id,
        sha256=record.sha256,
        phash=record.phash,
        embedding_model=record.embedding_model,
        ipfs_cid=record.ipfs_cid,
        ipfs_url=record.ipfs_url,
        timestamp_status=timestamp_status,
        status=record.status,
        created_at=record.created_at,
    )
