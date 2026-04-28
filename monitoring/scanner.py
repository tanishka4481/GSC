"""
PROVCHAIN — Scan Orchestrator
================================
Main entry point for propagation scanning. Coordinates all search providers:

    1. Google Custom Search (web + image + news)
    2. Wayback Machine (archived evidence)

For each candidate found, downloads the content and computes fingerprint
similarity against the registered asset using SEPARATE code paths:
    - pHash similarity (images only) — perceptual/pixel-level
    - Embedding similarity (all types) — semantic/conceptual

The scanner produces raw ScanHit objects. Interpretation and flagging
happen downstream in propagation_analyzer.py via match_decision().
"""

import io
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
import imagehash
import numpy as np
from PIL import Image

from core.config import get_settings
from core.exceptions import ScanError, StorageError
from monitoring.models import (
    ScanHit,
    ScanRecord,
    ScanSource,
    SearchResult,
)
from monitoring.google_search import search_web, search_images, search_news, get_quota_status
from monitoring.wayback import check_availability
from monitoring.domain_scorer import extract_domain_from_url
from registration.fingerprint import generate_content_summary
from registration.models import AssetRecord, SUPPORTED_IMAGE_TYPES

logger = logging.getLogger("provchain.scanner")


# =============================================================================
# Main Orchestrator
# =============================================================================

async def scan_asset(asset_id: str) -> ScanRecord:
    """
    Scan the web for copies of a registered asset.

    Pipeline:
        1. Fetch asset record from Firestore
        2. Build search queries from asset metadata
        3. Execute searches (Google web + image + news)
        4. For each result: download, fingerprint, compare
        5. Check Wayback Machine for archived evidence
        6. Return structured ScanRecord

    Args:
        asset_id: UUID of the registered asset.

    Returns:
        ScanRecord with all scan hits and metadata.

    Raises:
        ScanError: If asset not found or all search providers fail.
    """
    settings = get_settings()
    scan_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    logger.info("Scan started: asset_id=%s, scan_id=%s", asset_id, scan_id)

    # --- Stage 1: Fetch asset ---
    asset = _get_asset(asset_id)
    logger.info(
        "Asset loaded: filename=%s, type=%s, phash=%s, embedding=%s",
        asset.filename, asset.content_type,
        "yes" if asset.phash else "no",
        f"{len(asset.embedding)}d" if asset.embedding else "no",
    )

    # --- Stage 2: Build queries ---
    queries = await _build_search_queries(asset, settings)
    logger.info("Built %d search queries", len(queries))

    # --- Stage 3: Execute searches ---
    all_results: List[SearchResult] = []
    queries_used: List[str] = []

    for query_str, search_type in queries:
        try:
            if search_type == "image":
                results = await search_images(query_str, num=settings.GOOGLE_SEARCH_RESULTS_PER_QUERY)
            elif search_type == "news":
                results = await search_news(query_str, num=settings.GOOGLE_SEARCH_RESULTS_PER_QUERY)
            else:
                results = await search_web(query_str, num=settings.GOOGLE_SEARCH_RESULTS_PER_QUERY)

            all_results.extend(results)
            queries_used.append(f"[{search_type}] {query_str}")
            logger.info("Search [%s] returned %d results for '%s…'", search_type, len(results), query_str[:50])

        except ScanError as e:
            logger.warning("Search [%s] failed: %s", search_type, e.message)
            # Continue with other queries — don't fail the whole scan

    # --- Stage 4: Process results (download + fingerprint + compare) ---
    max_candidates = settings.SCAN_MAX_CANDIDATES
    scan_hits: List[ScanHit] = []
    seen_urls: set = set()  # Deduplicate across search types

    for result in all_results[:max_candidates * 2]:  # Over-fetch to account for failures
        if len(scan_hits) >= max_candidates:
            break

        if result.url in seen_urls:
            continue
        seen_urls.add(result.url)

        try:
            hit = await _process_search_result(result, asset, settings)
            if hit:
                scan_hits.append(hit)
        except Exception as e:
            logger.warning("Failed to process result %s: %s", result.url, e)

    # --- Stage 5: Wayback Machine evidence (non-blocking enrichment) ---
    for hit in scan_hits:
        try:
            snapshot = await check_availability(hit.url)
            if snapshot:
                logger.info("Wayback snapshot found for %s: %s", hit.url, snapshot.archive_url)
                # We note the Wayback availability but don't create a separate hit
        except Exception:
            pass  # Wayback check is best-effort

    # --- Build scan record ---
    record = ScanRecord(
        scan_id=scan_id,
        asset_id=asset_id,
        owner_id=asset.owner_id,
        queries_used=queries_used,
        total_results=len(scan_hits),
        hits=[hit.model_dump() for hit in scan_hits],
        status="completed",
        created_at=now,
    )

    logger.info(
        "Scan complete: scan_id=%s, hits=%d, quota=%s",
        scan_id, len(scan_hits), get_quota_status(),
    )

    return record, scan_hits, asset


# =============================================================================
# Query Builder
# =============================================================================

async def _build_search_queries(asset: AssetRecord, settings) -> List[Tuple[str, str]]:
    """
    Build search queries from asset metadata.

    Strategy:
        - Images: content-derived summary search + reverse lookup query
        - Text: use content snippet for web + news search
        - All: fallback to a generic search phrase if no semantic summary is available

    Args:
        asset: The registered asset record.

    Returns:
        List of (query_string, search_type) tuples.
    """
    queries = []
    filename_clean = os.path.splitext(asset.filename)[0].replace("_", " ").replace("-", " ")
    summary_query = (asset.content_summary or "").strip()

    if asset.content_type in SUPPORTED_IMAGE_TYPES:
        image_query = summary_query

        if not image_query and asset.ipfs_url:
            try:
                image_bytes = await _download_image(
                    asset.ipfs_url,
                    timeout=settings.SCAN_IMAGE_DOWNLOAD_TIMEOUT,
                )
                if image_bytes:
                    image_query = generate_content_summary(image_bytes, asset.content_type)
            except Exception:
                image_query = None

        if not image_query:
            image_query = "image"

        queries.append((image_query, "image"))
        queries.append((f'"{image_query}"', "web"))

    else:
        # Text/PDF: search by content-derived summary first, filename only as fallback.
        text_query = summary_query or filename_clean
        queries.append((text_query, "web"))

        # News search for the same content-derived query.
        queries.append((text_query, "news"))

    return queries


# =============================================================================
# Result Processor
# =============================================================================

async def _process_search_result(
    result: SearchResult,
    asset: AssetRecord,
    settings,
) -> Optional[ScanHit]:
    """
    Process a single search result: download, fingerprint, compare.

    Args:
        result: Raw search result from Google.
        asset: Registered asset to compare against.
        settings: Application settings.

    Returns:
        ScanHit with similarity scores, or None if processing fails.
    """
    now = datetime.now(timezone.utc).isoformat()
    domain = extract_domain_from_url(result.url)

    phash_sim: Optional[float] = None
    embedding_sim: Optional[float] = None
    has_attribution: Optional[bool] = None

    # --- pHash comparison (images only, separate code path) ---
    if (asset.content_type in SUPPORTED_IMAGE_TYPES
            and asset.phash
            and result.source in (ScanSource.GOOGLE_IMAGE, ScanSource.GOOGLE_WEB)):
        try:
            # Download the candidate image
            image_url = result.thumbnail_url or result.url
            image_bytes = await _download_image(
                image_url,
                timeout=settings.SCAN_IMAGE_DOWNLOAD_TIMEOUT,
            )

            if image_bytes:
                # Compute pHash of candidate
                candidate_phash = _compute_phash(image_bytes)
                if candidate_phash:
                    phash_sim = _compute_phash_similarity(asset.phash, candidate_phash)

        except Exception as e:
            logger.debug("pHash comparison failed for %s: %s", result.url, e)

    # --- Embedding comparison (all types, separate code path) ---
    if asset.embedding:
        try:
            # For image results: use the downloaded image to compute embedding
            # For text results: use the snippet text
            candidate_embedding = None

            if result.snippet and len(result.snippet.strip()) > 20:
                # Use snippet text for embedding comparison
                candidate_embedding = await _compute_snippet_embedding(result.snippet)

            if candidate_embedding:
                embedding_sim = _compute_embedding_similarity(
                    asset.embedding, candidate_embedding,
                )

        except Exception as e:
            logger.debug("Embedding comparison failed for %s: %s", result.url, e)

    # --- Attribution detection ---
    if result.snippet:
        has_attribution = _check_attribution(result.snippet, asset)

    return ScanHit(
        url=result.url,
        domain=domain,
        page_title=result.title,
        snippet=result.snippet,
        thumbnail_url=result.thumbnail_url,
        source=result.source,
        phash_similarity=phash_sim,
        embedding_similarity=embedding_sim,
        has_attribution=has_attribution,
        discovered_at=now,
    )


# =============================================================================
# Fingerprint Comparison — Separate Code Paths (Critical Rule)
# =============================================================================

def _compute_phash(image_bytes: bytes, hash_size: int = 16) -> Optional[str]:
    """
    Compute pHash of downloaded candidate image.

    Separate from registration/fingerprint.py's compute_phash to avoid
    import cycles. Uses the same algorithm.

    Args:
        image_bytes: Raw image bytes.
        hash_size: pHash grid size (must match registration setting).

    Returns:
        Hex string of the pHash, or None on failure.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        phash = imagehash.phash(img, hash_size=hash_size)
        return str(phash)
    except Exception as e:
        logger.debug("pHash computation failed: %s", e)
        return None


def _compute_phash_similarity(phash1: str, phash2: str) -> float:
    """
    Compute normalized similarity between two pHash hex strings.

    Uses Hamming distance: count of differing bits.
    Similarity = 1 - (hamming_distance / total_bits)

    Args:
        phash1: First pHash hex string (from registered asset).
        phash2: Second pHash hex string (from candidate).

    Returns:
        Similarity score 0.0 to 1.0 (1.0 = identical).
    """
    try:
        hash1 = imagehash.hex_to_hash(phash1)
        hash2 = imagehash.hex_to_hash(phash2)

        # Hamming distance = number of differing bits
        hamming_dist = hash1 - hash2
        total_bits = hash1.hash.size

        similarity = 1.0 - (hamming_dist / total_bits)
        return max(0.0, min(1.0, similarity))

    except Exception as e:
        logger.debug("pHash similarity computation failed: %s", e)
        return 0.0


def _compute_embedding_similarity(emb1: List[float], emb2: List[float]) -> float:
    """
    Compute cosine similarity between two embedding vectors.

    cosine_similarity = dot(a, b) / (norm(a) * norm(b))

    Args:
        emb1: Registered asset's embedding vector.
        emb2: Candidate's embedding vector.

    Returns:
        Cosine similarity -1.0 to 1.0 (1.0 = identical direction).
    """
    try:
        a = np.array(emb1, dtype=np.float64)
        b = np.array(emb2, dtype=np.float64)

        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        similarity = float(np.dot(a, b) / (norm_a * norm_b))
        return max(-1.0, min(1.0, similarity))

    except Exception as e:
        logger.debug("Embedding similarity computation failed: %s", e)
        return 0.0


async def _compute_snippet_embedding(snippet: str) -> Optional[List[float]]:
    """
    Compute Gemini embedding for a text snippet.

    Uses the same Gemini embedding model as registration, but handles
    failures gracefully since snippet embedding is best-effort.

    Args:
        snippet: Text snippet from search result.

    Returns:
        Embedding vector, or None on failure.
    """
    settings = get_settings()

    if not settings.GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        result = client.models.embed_content(
            model=settings.GEMINI_EMBEDDING_MODEL,
            contents=snippet,
            config=types.EmbedContentConfig(
                output_dimensionality=settings.GEMINI_EMBEDDING_DIMENSIONS,
            ),
        )
        return result.embeddings[0].values

    except Exception as e:
        logger.debug("Snippet embedding failed: %s", e)
        return None


# =============================================================================
# Attribution Detection
# =============================================================================

def _check_attribution(snippet: str, asset: AssetRecord) -> bool:
    """
    Heuristic check whether a search result snippet credits the original source.

    Looks for the asset owner ID, filename, or common attribution patterns
    in the page snippet. This is a rough heuristic — false negatives are
    expected (attribution might be on the page but not in the snippet).

    Args:
        snippet: Text snippet from the search result.
        asset: Registered asset record.

    Returns:
        True if attribution is detected, False otherwise.
    """
    snippet_lower = snippet.lower()

    # Check for owner reference
    if asset.owner_id and asset.owner_id != "anonymous":
        if asset.owner_id.lower() in snippet_lower:
            return True

    # Check for content summary reference first so scans do not bias on filenames.
    if asset.content_summary:
        summary_clean = asset.content_summary.lower().strip()
        if len(summary_clean) > 3 and summary_clean in snippet_lower:
            return True

    # Check for filename reference as a fallback when no summary exists.
    filename_clean = os.path.splitext(asset.filename)[0].lower().replace("_", " ").replace("-", " ")
    if len(filename_clean) > 3 and filename_clean in snippet_lower:
        return True

    # Common attribution patterns
    attribution_signals = [
        "source:", "credit:", "courtesy:", "photo:",
        "image credit", "photo credit", "via ",
        "© ", "copyright", "all rights reserved",
        "reprinted with permission", "used with permission",
        "originally published", "first published",
    ]
    for signal in attribution_signals:
        if signal in snippet_lower:
            return True

    return False


# =============================================================================
# Helpers
# =============================================================================

async def _download_image(url: str, timeout: float = 10.0) -> Optional[bytes]:
    """
    Download an image from a URL with timeout and size limits.

    Args:
        url: Image URL to download.
        timeout: Request timeout in seconds.

    Returns:
        Image bytes, or None if download fails.
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=5),
        ) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "PROVCHAIN-Scanner/1.0"},
            )

            if response.status_code != 200:
                return None

            # Don't download files > 10MB
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > 10 * 1024 * 1024:
                return None

            content = response.content
            if len(content) > 10 * 1024 * 1024:
                return None

            return content

    except Exception as e:
        logger.debug("Image download failed for %s: %s", url, e)
        return None


def _get_asset(asset_id: str) -> AssetRecord:
    """
    Fetch asset record from Firestore.

    Args:
        asset_id: UUID of the asset.

    Returns:
        AssetRecord.

    Raises:
        ScanError: If asset not found or Firestore unavailable.
    """
    try:
        from registration.registry import get_asset
        return get_asset(asset_id)
    except Exception as e:
        raise ScanError(
            message=f"Failed to fetch asset for scanning: {e}",
            detail={"asset_id": asset_id},
        )
