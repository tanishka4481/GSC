"""
PROVCHAIN — Dual Fingerprinting
=================================
Two SEPARATE code paths (critical rule):

1. pHash  — perceptual hash for pixel-level similarity (images only)
2. Gemini — semantic embedding for conceptual similarity (all types)

These are intentionally decoupled. pHash catches resized/cropped/recompressed
copies; Gemini embedding catches derivative works and rephrased content.
"""

import io
import logging
from typing import List, Optional

import imagehash
from PIL import Image
from google import genai
from google.genai import types

from core.config import get_settings
from core.exceptions import FingerprintError
from registration.models import AssetFingerprint, SUPPORTED_IMAGE_TYPES

logger = logging.getLogger("provchain.fingerprint")


# =============================================================================
# Code Path 1: Perceptual Hash (pHash)
# =============================================================================

def compute_phash(image_bytes: bytes, hash_size: int = 16) -> str:
    """
    Compute perceptual hash of an image using DCT-based pHash.

    The pHash is robust to resizing, mild cropping, recompression,
    and minor color adjustments. Two images with a small Hamming distance
    between their pHash values are visually similar.

    Args:
        image_bytes: Raw image bytes (any PIL-supported format).
        hash_size: Hash grid size. 16 → 256-bit hash (64 hex chars).
                   Higher = more discriminative but more sensitive to changes.

    Returns:
        Hex string representation of the perceptual hash.

    Raises:
        FingerprintError: If image cannot be processed.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        phash = imagehash.phash(img, hash_size=hash_size)
        hex_str = str(phash)

        logger.debug("pHash computed: %s… (hash_size=%d)", hex_str[:16], hash_size)
        return hex_str

    except Exception as e:
        raise FingerprintError(
            message=f"pHash computation failed: {e}",
            detail={"hash_size": hash_size},
        )


# =============================================================================
# Code Path 2: Gemini Embedding
# =============================================================================

def compute_embedding(file_bytes: bytes, content_type: str) -> List[float]:
    """
    Generate a semantic embedding vector via Gemini API.

    Uses gemini-embedding-2 (multimodal) to map the content into a
    unified vector space. The embedding captures semantic meaning,
    enabling detection of derivative works and rephrased content.

    Args:
        file_bytes: Raw file bytes.
        content_type: MIME type (determines how content is sent to Gemini).

    Returns:
        List of floats — the embedding vector (768 dimensions by default).

    Raises:
        FingerprintError: If embedding generation fails or API key missing.
    """
    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        raise FingerprintError(
            message="Gemini API key not configured — cannot generate embedding",
            detail={"setting": "GEMINI_API_KEY"},
        )

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Build content based on type
        if content_type in SUPPORTED_IMAGE_TYPES:
            # Image: send as inline image data
            content = types.Content(
                parts=[
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=content_type,
                    )
                ]
            )
        elif content_type.startswith("text/"):
            # Text: decode and send as text
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1")
            content = text
        elif content_type == "application/pdf":
            # PDF: send as inline bytes
            content = types.Content(
                parts=[
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=content_type,
                    )
                ]
            )
        else:
            raise FingerprintError(
                message=f"Unsupported content type for embedding: {content_type}",
                detail={"content_type": content_type},
            )

        result = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=content,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.GEMINI_EMBEDDING_DIMENSIONS,
            ),
        )

        embedding = result.embeddings[0].values

        logger.info(
            "Embedding generated: model=%s, dims=%d, type=%s",
            settings.GEMINI_EMBEDDING_MODEL,
            len(embedding),
            content_type,
        )
        return embedding

    except FingerprintError:
        raise  # Re-raise our own errors
    except Exception as e:
        raise FingerprintError(
            message=f"Gemini embedding generation failed: {e}",
            detail={
                "model": settings.GEMINI_EMBEDDING_MODEL,
                "content_type": content_type,
            },
        )


# =============================================================================
# Orchestrator
# =============================================================================

def generate_fingerprints(file_bytes: bytes, content_type: str) -> AssetFingerprint:
    """
    Run both fingerprinting paths and return combined results.

    - pHash: only for image/* content types
    - Embedding: for all supported content types

    Each path runs independently. If one fails, the other still produces
    a result (with None for the failed path + a warning logged).

    Args:
        file_bytes: Raw file bytes (original, not normalized).
        content_type: MIME type of the file.

    Returns:
        AssetFingerprint with phash (Optional) and embedding (Optional).
    """
    settings = get_settings()
    phash_result: Optional[str] = None
    embedding_result: Optional[List[float]] = None
    embedding_model: Optional[str] = None

    # --- Path 1: pHash (images only) ---
    if content_type in SUPPORTED_IMAGE_TYPES:
        try:
            phash_result = compute_phash(file_bytes)
        except FingerprintError as e:
            logger.warning("pHash failed (continuing with embedding): %s", e.message)

    # --- Path 2: Gemini embedding (all types) ---
    try:
        embedding_result = compute_embedding(file_bytes, content_type)
        embedding_model = settings.GEMINI_EMBEDDING_MODEL
    except FingerprintError as e:
        logger.warning("Gemini embedding failed (continuing without): %s", e.message)

    # At least one fingerprint should succeed
    if phash_result is None and embedding_result is None:
        raise FingerprintError(
            message="Both fingerprinting paths failed — cannot register asset",
            detail={"content_type": content_type},
        )

    logger.info(
        "Fingerprints generated: phash=%s, embedding=%s",
        "yes" if phash_result else "no",
        f"{len(embedding_result)}d" if embedding_result else "no",
    )

    return AssetFingerprint(
        phash=phash_result,
        embedding=embedding_result,
        embedding_model=embedding_model,
    )
