"""
PROVCHAIN — Asset Registry
============================
Central orchestrator that ties the entire registration pipeline together.

register_asset() is the main entry point:
    Upload → Hash → Fingerprint → Timestamp (Bitcoin) → Pin (IPFS) → Store (Firestore)

Also provides Firestore CRUD for asset records.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from core.config import get_settings
from core.exceptions import RegistrationError, StorageError
from registration.hasher import hash_asset
from registration.fingerprint import generate_fingerprints
from registration.timestamp import create_timestamp
from registration.ipfs_client import pin_to_ipfs, get_ipfs_url
from registration.models import AssetRecord, SUPPORTED_CONTENT_TYPES

logger = logging.getLogger("provchain.registry")


# =============================================================================
# Firestore Helpers
# =============================================================================

def _get_db():
    """
    Get the Firestore client.

    Returns the firestore client from the initialized Firebase Admin SDK.
    If Firebase is not initialized, raises StorageError.
    """
    try:
        from firebase_admin import firestore
        settings = get_settings()
        return firestore.client(database_id=settings.FIRESTORE_DATABASE_ID)
    except Exception as e:
        raise StorageError(
            message=f"Firestore client unavailable: {e}",
            detail={"hint": "Ensure Firebase Admin SDK is initialized in main.py lifespan"},
        )


ASSETS_COLLECTION = "assets"


# =============================================================================
# Main Registration Orchestrator
# =============================================================================

async def register_asset(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    owner_id: str,
) -> AssetRecord:
    """
    Register a digital asset through the full pipeline.

    Pipeline stages (in order):
    1. Validate content type
    2. Hash the file (with normalization)
    3. Check for duplicates (same SHA-256 already registered)
    4. Generate fingerprints (pHash + Gemini embedding)
    5. Create blockchain timestamp (OpenTimestamps → Bitcoin)
    6. Pin to IPFS via Pinata
    7. Store everything in Firestore

    Args:
        file_bytes: Raw uploaded file bytes.
        filename: Original filename from the upload.
        content_type: MIME type (e.g., 'image/jpeg', 'text/plain').
        owner_id: Firebase UID or 'anonymous'.

    Returns:
        Complete AssetRecord with all fields populated.

    Raises:
        RegistrationError: If content type unsupported or duplicate found.
        HashingError: If hashing/normalization fails.
        FingerprintError: If both fingerprinting paths fail.
        TimestampError: On critical timestamp failure.
        StorageError: If Firestore/IPFS operations fail.
    """
    # --- Stage 1: Validate content type ---
    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise RegistrationError(
            message=f"Unsupported content type: {content_type}",
            detail={
                "content_type": content_type,
                "supported": sorted(SUPPORTED_CONTENT_TYPES),
            },
        )

    logger.info(
        "Starting registration: filename=%s, type=%s, size=%d, owner=%s",
        filename,
        content_type,
        len(file_bytes),
        owner_id,
    )

    # --- Stage 2: Hash ---
    asset_hash = hash_asset(file_bytes, content_type)
    logger.info("Stage 2/6 complete: SHA-256=%s…", asset_hash.sha256[:16])

    # --- Stage 3: Duplicate check ---
    existing_id = asset_exists(asset_hash.sha256)
    if existing_id:
        raise RegistrationError(
            message="Duplicate asset — this file has already been registered",
            detail={
                "existing_asset_id": existing_id,
                "sha256": asset_hash.sha256,
            },
        )
    logger.info("Stage 3/6 complete: No duplicate found")

    # --- Stage 4: Fingerprint ---
    fingerprints = generate_fingerprints(file_bytes, content_type)
    logger.info(
        "Stage 4/6 complete: phash=%s, embedding=%s",
        "yes" if fingerprints.phash else "no",
        f"{len(fingerprints.embedding)}d" if fingerprints.embedding else "no",
    )

    # --- Stage 5: Timestamp ---
    timestamp_proof = create_timestamp(asset_hash.sha256)
    logger.info("Stage 5/6 complete: timestamp_status=%s", timestamp_proof.status)

    # --- Stage 6a: IPFS Pin ---
    ipfs_cid: Optional[str] = None
    ipfs_url: Optional[str] = None
    try:
        ipfs_result = await pin_to_ipfs(
            file_bytes=file_bytes,
            filename=filename,
            metadata={
                "sha256": asset_hash.sha256,
                "owner_id": owner_id,
                "content_type": content_type,
            },
        )
        if ipfs_result:
            ipfs_cid = ipfs_result.cid
            ipfs_url = get_ipfs_url(ipfs_result.cid)
    except StorageError as e:
        # IPFS pinning is non-critical — log and continue
        logger.warning("IPFS pinning failed (continuing): %s", e.message)

    logger.info(
        "Stage 6a complete: ipfs_cid=%s",
        ipfs_cid or "(skipped)",
    )

    # --- Stage 6b: Firestore Write ---
    asset_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    record = AssetRecord(
        asset_id=asset_id,
        owner_id=owner_id,
        filename=filename,
        content_type=content_type,
        file_size=asset_hash.file_size,
        sha256=asset_hash.sha256,
        phash=fingerprints.phash,
        embedding=fingerprints.embedding,
        embedding_model=fingerprints.embedding_model,
        content_summary=fingerprints.content_summary,
        ipfs_cid=ipfs_cid,
        ipfs_url=ipfs_url,
        timestamp_proof=timestamp_proof.model_dump(),
        status="registered",
        created_at=now,
        updated_at=now,
    )

    try:
        db = _get_db()
        doc_ref = db.collection(ASSETS_COLLECTION).document(asset_id)
        doc_ref.set(record.to_firestore_dict())
        logger.info("Stage 6b complete: Firestore doc written, asset_id=%s", asset_id)
    except StorageError:
        raise
    except Exception as e:
        raise StorageError(
            message=f"Firestore write failed: {e}",
            detail={"asset_id": asset_id},
        )

    logger.info(
        "Registration complete: asset_id=%s, sha256=%s…, owner=%s",
        asset_id,
        asset_hash.sha256[:16],
        owner_id,
    )

    return record


# =============================================================================
# Read Operations
# =============================================================================

def get_asset(asset_id: str) -> AssetRecord:
    """
    Fetch a single asset record from Firestore by asset_id.

    Args:
        asset_id: UUID of the asset.

    Returns:
        AssetRecord if found.

    Raises:
        RegistrationError: If asset not found.
        StorageError: If Firestore read fails.
    """
    try:
        db = _get_db()
        doc = db.collection(ASSETS_COLLECTION).document(asset_id).get()

        if not doc.exists:
            raise RegistrationError(
                message=f"Asset not found: {asset_id}",
                detail={"asset_id": asset_id},
                status_code=404,
            )

        data = doc.to_dict()
        return AssetRecord(**data)

    except RegistrationError:
        raise
    except Exception as e:
        raise StorageError(
            message=f"Firestore read failed: {e}",
            detail={"asset_id": asset_id},
        )


def get_assets_by_owner(owner_id: str) -> List[AssetRecord]:
    """
    List all assets registered by a specific owner.

    Args:
        owner_id: Firebase UID or 'anonymous'.

    Returns:
        List of AssetRecord objects (may be empty).

    Raises:
        StorageError: If Firestore query fails.
    """
    try:
        db = _get_db()
        query = (
            db.collection(ASSETS_COLLECTION)
            .where("owner_id", "==", owner_id)
            .order_by("created_at", direction="DESCENDING")
        )

        records = []
        for doc in query.stream():
            records.append(AssetRecord(**doc.to_dict()))

        logger.info("Found %d assets for owner=%s", len(records), owner_id)
        return records

    except Exception as e:
        raise StorageError(
            message=f"Firestore query failed: {e}",
            detail={"owner_id": owner_id},
        )


def asset_exists(sha256: str) -> Optional[str]:
    """
    Check if an asset with the given SHA-256 digest is already registered.

    Args:
        sha256: SHA-256 hex digest to search for.

    Returns:
        asset_id if found, None otherwise.

    Raises:
        StorageError: If Firestore query fails.
    """
    try:
        db = _get_db()
        query = (
            db.collection(ASSETS_COLLECTION)
            .where("sha256", "==", sha256)
            .limit(1)
        )

        for doc in query.stream():
            existing_id = doc.to_dict().get("asset_id", doc.id)
            logger.info("Duplicate found: sha256=%s…, existing_id=%s", sha256[:16], existing_id)
            return existing_id

        return None

    except Exception as e:
        raise StorageError(
            message=f"Duplicate check failed: {e}",
            detail={"sha256": sha256},
        )
