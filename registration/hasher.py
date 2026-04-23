"""
PROVCHAIN — Content Hashing
=============================
Produces a deterministic SHA-256 digest for any uploaded file.
Images are normalized (strip EXIF, resize, PNG) so the same visual
content always produces the same hash regardless of metadata.

Rule: Never hardcode keys — all config from core.config.
"""

import hashlib
import io
import logging
from typing import Optional

from PIL import Image, ImageOps

from core.config import get_settings
from core.exceptions import HashingError
from registration.models import AssetHash, SUPPORTED_IMAGE_TYPES

logger = logging.getLogger("provchain.hasher")

# Maximum dimension for normalized images (longest side)
NORMALIZE_MAX_DIM = 512


def compute_sha256(data: bytes) -> str:
    """
    Compute the SHA-256 hex digest of raw bytes.

    Args:
        data: Raw file bytes.

    Returns:
        64-character lowercase hex digest string.
    """
    return hashlib.sha256(data).hexdigest()


def normalize_image(file_bytes: bytes) -> bytes:
    """
    Normalize an image for consistent hashing:
    1. Strip EXIF and metadata
    2. Apply EXIF orientation, then discard all EXIF
    3. Resize longest side to NORMALIZE_MAX_DIM px (preserve aspect ratio)
    4. Convert to RGB PNG

    This ensures the same visual content → same hash, regardless of
    camera metadata, compression artifacts, or orientation flags.

    Args:
        file_bytes: Raw image bytes (any supported format).

    Returns:
        Normalized PNG bytes.

    Raises:
        HashingError: If image cannot be opened or processed.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))

        # Apply EXIF orientation (auto-rotate), then strip EXIF
        img = ImageOps.exif_transpose(img)

        # Convert to RGB (drop alpha, handle palette modes)
        if img.mode not in ("RGB",):
            img = img.convert("RGB")

        # Resize if larger than max dimension
        if max(img.size) > NORMALIZE_MAX_DIM:
            img.thumbnail((NORMALIZE_MAX_DIM, NORMALIZE_MAX_DIM), Image.LANCZOS)

        # Export as PNG (lossless, no metadata)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        normalized = buffer.getvalue()

        logger.debug(
            "Image normalized: %dx%d → %dx%d, %d → %d bytes",
            *Image.open(io.BytesIO(file_bytes)).size,
            *img.size,
            len(file_bytes),
            len(normalized),
        )
        return normalized

    except Exception as e:
        raise HashingError(
            message=f"Image normalization failed: {e}",
            detail={"original_size": len(file_bytes)},
        )


def normalize_text(file_bytes: bytes) -> bytes:
    """
    Normalize text content for consistent hashing:
    1. Decode to UTF-8 (fallback: latin-1)
    2. Normalize line endings to LF
    3. Strip trailing whitespace from each line
    4. Strip leading/trailing blank lines
    5. Re-encode to UTF-8

    Args:
        file_bytes: Raw text file bytes.

    Returns:
        Normalized UTF-8 bytes.

    Raises:
        HashingError: If text cannot be decoded.
    """
    try:
        # Try UTF-8 first, fall back to latin-1
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1")

        # Normalize line endings to LF
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Strip trailing whitespace per line, strip leading/trailing blank lines
        lines = [line.rstrip() for line in text.split("\n")]
        text = "\n".join(lines).strip()

        normalized = text.encode("utf-8")
        logger.debug(
            "Text normalized: %d → %d bytes",
            len(file_bytes),
            len(normalized),
        )
        return normalized

    except Exception as e:
        raise HashingError(
            message=f"Text normalization failed: {e}",
            detail={"original_size": len(file_bytes)},
        )


def hash_asset(file_bytes: bytes, content_type: str) -> AssetHash:
    """
    Entry point: normalize the file (if applicable), then hash.

    For images: normalize → hash the normalized PNG
    For text:   normalize → hash the normalized UTF-8
    For others: hash the raw bytes (PDF, etc.)

    Also enforces the max upload size from config.

    Args:
        file_bytes: Raw uploaded file bytes.
        content_type: MIME type string (e.g. 'image/jpeg', 'text/plain').

    Returns:
        AssetHash with sha256, normalized bytes, content_type, and file_size.

    Raises:
        HashingError: On normalization or hashing failure.
        HashingError: If file exceeds max upload size.
    """
    settings = get_settings()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    if len(file_bytes) > max_bytes:
        raise HashingError(
            message=f"File too large: {len(file_bytes)} bytes exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit",
            detail={
                "file_size": len(file_bytes),
                "max_size": max_bytes,
            },
        )

    if len(file_bytes) == 0:
        raise HashingError(
            message="Empty file — nothing to hash",
            detail={"file_size": 0},
        )

    try:
        # Determine which normalization path to use
        if content_type in SUPPORTED_IMAGE_TYPES:
            normalized = normalize_image(file_bytes)
        elif content_type.startswith("text/"):
            normalized = normalize_text(file_bytes)
        else:
            # PDF and other binary formats — hash as-is
            normalized = file_bytes

        sha256 = compute_sha256(normalized)

        logger.info(
            "Asset hashed: type=%s, size=%d, sha256=%s…",
            content_type,
            len(file_bytes),
            sha256[:16],
        )

        return AssetHash(
            sha256=sha256,
            normalized_bytes=normalized,
            content_type=content_type,
            file_size=len(file_bytes),
        )

    except HashingError:
        raise  # Re-raise our own errors
    except Exception as e:
        raise HashingError(
            message=f"Hashing failed: {e}",
            detail={"content_type": content_type, "file_size": len(file_bytes)},
        )
