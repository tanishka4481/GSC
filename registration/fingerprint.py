"""
PROVCHAIN — Dual Fingerprinting
=================================
Two SEPARATE code paths (critical rule):

1. pHash  — perceptual hash for pixel-level similarity (images only)
2. Gemini — semantic embedding for conceptual similarity (all types)

These are intentionally decoupled. pHash catches resized/cropped/recompressed
copies; Gemini embedding catches derivative works and rephrased content.
"""

import hashlib
import io
import logging
import re
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
        logger.warning("Gemini API key not configured, using local fallback embedding")
        fallback_embedding = _fallback_embedding(file_bytes, content_type)
        if fallback_embedding is not None:
            return fallback_embedding
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
        logger.warning("Gemini embedding generation failed, using local fallback: %s", e)
        fallback_embedding = _fallback_embedding(file_bytes, content_type)
        if fallback_embedding is not None:
            return fallback_embedding
        raise FingerprintError(
            message=f"Gemini embedding generation failed: {e}",
            detail={
                "model": settings.GEMINI_EMBEDDING_MODEL,
                "content_type": content_type,
            },
        )


def generate_image_summary(file_bytes: bytes, content_type: str) -> Optional[str]:
    """
    Generate a short content-derived summary for an image.

    This is used only for search query construction. It intentionally ignores
    filenames so the scan pipeline keys off the actual image contents.
    """
    settings = get_settings()

    if content_type not in SUPPORTED_IMAGE_TYPES or not settings.GEMINI_API_KEY:
        return None

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = (
            "Describe the main subject and visual style of this image in 3 to 8 "
            "concise keywords. Do not mention file names, filenames, or metadata. "
            "Return only the phrase."
        )
        response = client.models.generate_content(
            model=settings.GEMINI_VISION_MODEL,
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=file_bytes,
                    mime_type=content_type,
                ),
            ],
        )

        text = getattr(response, "text", "") or ""
        summary = " ".join(text.split()).strip()
        return summary or None

    except Exception as e:
        logger.warning("Image summary generation failed (continuing without): %s", e)
        return None


def generate_content_summary(file_bytes: bytes, content_type: str) -> Optional[str]:
    """
    Generate a short content-derived search summary for any supported asset.

    Images get a Gemini vision summary. Text and PDF assets get an extracted
    keyword summary so search queries reflect the actual content, not the filename.
    """
    if content_type in SUPPORTED_IMAGE_TYPES:
        return generate_image_summary(file_bytes, content_type)

    if content_type.startswith("text/"):
        return _summarize_text(file_bytes)

    if content_type == "application/pdf":
        extracted_text = _extract_pdf_text(file_bytes)
        if extracted_text:
            return _summarize_text(extracted_text.encode("utf-8"))

    return None


def _fallback_embedding(file_bytes: bytes, content_type: str) -> Optional[List[float]]:
    """
    Deterministic local fallback embedding.

    This keeps registration working when Gemini is unavailable. It is not a
    semantic model, but it is stable and content-derived.
    """
    settings = get_settings()
    dimensions = settings.GEMINI_EMBEDDING_DIMENSIONS
    vector = [0.0] * dimensions

    try:
        tokens: List[str] = []

        if content_type.startswith("text/"):
            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = file_bytes.decode("latin-1", errors="ignore")
            tokens = re.findall(r"[a-z0-9]+", text.lower())
        elif content_type == "application/pdf":
            tokens = _extract_pdf_tokens(file_bytes)

        if tokens:
            for token in tokens[:4000]:
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % dimensions
                secondary = int.from_bytes(digest[4:8], "big") % dimensions
                vector[index] += 1.0
                vector[secondary] += 0.5
                if len(token) > 6:
                    vector[(index + len(token)) % dimensions] += 0.25
        else:
            for offset in range(0, len(file_bytes), 32):
                chunk = file_bytes[offset:offset + 32]
                digest = hashlib.sha256(chunk).digest()
                index = int.from_bytes(digest[:4], "big") % dimensions
                secondary = int.from_bytes(digest[4:8], "big") % dimensions
                vector[index] += 1.0
                vector[secondary] += 0.5

        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0:
            return None

        return [value / norm for value in vector]

    except Exception as e:
        logger.debug("Local embedding fallback failed: %s", e)
        return None


def _summarize_text(file_bytes: bytes) -> Optional[str]:
    """Create a compact keyword summary from text content."""
    try:
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="ignore")

        stopwords = {
            "the", "and", "for", "with", "from", "that", "this", "these",
            "those", "there", "their", "into", "onto", "about", "above",
            "below", "between", "after", "before", "through", "during",
            "paper", "study", "research", "results", "conclusion", "abstract",
            "introduction", "method", "methods", "discussion", "analysis",
        }
        tokens = re.findall(r"[a-z0-9]{3,}", text.lower())
        keywords: List[str] = []
        for token in tokens:
            if token in stopwords:
                continue
            if token not in keywords:
                keywords.append(token)
            if len(keywords) >= 8:
                break

        if not keywords:
            return None

        return " ".join(keywords)

    except Exception as e:
        logger.debug("Text summary generation failed: %s", e)
        return None


def _extract_pdf_text(file_bytes: bytes) -> str:
    """Best-effort PDF text extraction for search summaries."""
    try:
        from pypdf import PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader
        except Exception:
            return ""

    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        chunks = []
        for page in reader.pages[:5]:
            try:
                chunks.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(chunks)
    except Exception as e:
        logger.debug("PDF text extraction failed: %s", e)
        return ""


def _extract_pdf_tokens(file_bytes: bytes) -> List[str]:
    """Best-effort PDF text extraction for the fallback embedding."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        extracted_text = []
        for page in reader.pages[:5]:
            try:
                extracted_text.append(page.extract_text() or "")
            except Exception:
                continue
        text = "\n".join(extracted_text).lower()
        return re.findall(r"[a-z0-9]+", text)
    except Exception:
        return []


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
    content_summary: Optional[str] = None

    # --- Path 1: pHash (images only) ---
    if content_type in SUPPORTED_IMAGE_TYPES:
        try:
            phash_result = compute_phash(file_bytes)
        except FingerprintError as e:
            logger.warning("pHash failed (continuing with embedding): %s", e.message)

    content_summary = generate_content_summary(file_bytes, content_type)

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
        content_summary=content_summary,
    )
