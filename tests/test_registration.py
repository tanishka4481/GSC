"""
PROVCHAIN — Phase 2 Unit Tests
=================================
Tests for the registration pipeline: hasher, fingerprint, timestamp.

Note: Tests that hit external APIs (Gemini, Pinata, Firestore) use mocks.
Run with: pytest tests/test_registration.py -v
"""

import hashlib
import io
import os
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from PIL import Image

# Set test environment before importing modules
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("MAX_UPLOAD_SIZE_MB", "100")


# =============================================================================
# Hasher Tests
# =============================================================================

class TestComputeSha256:
    """Test registration.hasher.compute_sha256"""

    def test_deterministic_output(self):
        """Same input always produces same hash."""
        from registration.hasher import compute_sha256

        data = b"hello provchain"
        hash1 = compute_sha256(data)
        hash2 = compute_sha256(data)
        assert hash1 == hash2

    def test_correct_hash(self):
        """Output matches hashlib directly."""
        from registration.hasher import compute_sha256

        data = b"test content for hashing"
        expected = hashlib.sha256(data).hexdigest()
        assert compute_sha256(data) == expected

    def test_hex_format(self):
        """Output is a 64-char lowercase hex string."""
        from registration.hasher import compute_sha256

        result = compute_sha256(b"anything")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_different_inputs_different_hashes(self):
        """Different inputs produce different hashes."""
        from registration.hasher import compute_sha256

        hash1 = compute_sha256(b"input a")
        hash2 = compute_sha256(b"input b")
        assert hash1 != hash2


class TestNormalizeImage:
    """Test registration.hasher.normalize_image"""

    def _make_test_image(self, width=800, height=600, fmt="JPEG") -> bytes:
        """Create a test image in memory."""
        img = Image.new("RGB", (width, height), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    def test_strips_exif_produces_png(self):
        """Normalized output is PNG format."""
        from registration.hasher import normalize_image

        jpeg_bytes = self._make_test_image(fmt="JPEG")
        result = normalize_image(jpeg_bytes)

        # Verify it's a valid PNG
        img = Image.open(io.BytesIO(result))
        assert img.format == "PNG"

    def test_resizes_large_images(self):
        """Images larger than 512px are resized."""
        from registration.hasher import normalize_image

        large_bytes = self._make_test_image(width=2000, height=1500)
        result = normalize_image(large_bytes)

        img = Image.open(io.BytesIO(result))
        assert max(img.size) <= 512

    def test_small_images_not_upscaled(self):
        """Images smaller than 512px are NOT upscaled."""
        from registration.hasher import normalize_image

        small_bytes = self._make_test_image(width=100, height=100)
        result = normalize_image(small_bytes)

        img = Image.open(io.BytesIO(result))
        assert max(img.size) <= 100

    def test_consistent_output(self):
        """Same image normalized twice produces same bytes."""
        from registration.hasher import normalize_image

        original = self._make_test_image()
        norm1 = normalize_image(original)
        norm2 = normalize_image(original)
        assert norm1 == norm2

    def test_invalid_image_raises(self):
        """Non-image bytes raise HashingError."""
        from registration.hasher import normalize_image
        from core.exceptions import HashingError

        with pytest.raises(HashingError):
            normalize_image(b"not an image")


class TestNormalizeText:
    """Test registration.hasher.normalize_text"""

    def test_normalizes_crlf(self):
        """CRLF line endings → LF."""
        from registration.hasher import normalize_text

        result = normalize_text(b"line1\r\nline2\r\n")
        assert b"\r" not in result
        assert result == b"line1\nline2"

    def test_strips_trailing_whitespace(self):
        """Trailing spaces on lines are removed."""
        from registration.hasher import normalize_text

        result = normalize_text(b"hello   \nworld  ")
        assert result == b"hello\nworld"

    def test_strips_outer_blank_lines(self):
        """Leading/trailing blank lines are stripped."""
        from registration.hasher import normalize_text

        result = normalize_text(b"\n\nhello\nworld\n\n")
        assert result == b"hello\nworld"


class TestHashAsset:
    """Test registration.hasher.hash_asset"""

    def _make_test_image(self) -> bytes:
        img = Image.new("RGB", (100, 100), color=(0, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

    def test_image_hash(self):
        """Image files produce a valid AssetHash."""
        from registration.hasher import hash_asset

        image_bytes = self._make_test_image()
        result = hash_asset(image_bytes, "image/jpeg")

        assert len(result.sha256) == 64
        assert result.content_type == "image/jpeg"
        assert result.file_size == len(image_bytes)

    def test_text_hash(self):
        """Text files produce a valid AssetHash."""
        from registration.hasher import hash_asset

        text_bytes = b"Sample article content for testing.\n"
        result = hash_asset(text_bytes, "text/plain")

        assert len(result.sha256) == 64
        assert result.content_type == "text/plain"

    def test_empty_file_raises(self):
        """Empty files raise HashingError."""
        from registration.hasher import hash_asset
        from core.exceptions import HashingError

        with pytest.raises(HashingError, match="Empty file"):
            hash_asset(b"", "text/plain")

    def test_oversized_file_raises(self):
        """Files exceeding MAX_UPLOAD_SIZE_MB raise HashingError."""
        from registration.hasher import hash_asset
        from core.exceptions import HashingError

        # Create bytes just over the limit (use a small limit for testing)
        with patch("registration.hasher.get_settings") as mock_settings:
            mock_settings.return_value.MAX_UPLOAD_SIZE_MB = 1  # 1 MB limit
            big_data = b"x" * (1024 * 1024 + 1)  # 1 MB + 1 byte

            with pytest.raises(HashingError, match="File too large"):
                hash_asset(big_data, "text/plain")


# =============================================================================
# Fingerprint Tests
# =============================================================================

class TestComputePhash:
    """Test registration.fingerprint.compute_phash"""

    def _make_test_image(self) -> bytes:
        img = Image.new("RGB", (200, 200), color=(128, 64, 32))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_returns_hex_string(self):
        """pHash returns a non-empty hex string."""
        from registration.fingerprint import compute_phash

        result = compute_phash(self._make_test_image())
        assert isinstance(result, str)
        assert len(result) > 0
        assert all(c in "0123456789abcdef" for c in result)

    def test_consistent_for_same_image(self):
        """Same image always produces same pHash."""
        from registration.fingerprint import compute_phash

        img_bytes = self._make_test_image()
        hash1 = compute_phash(img_bytes)
        hash2 = compute_phash(img_bytes)
        assert hash1 == hash2

    def test_invalid_image_raises(self):
        """Non-image bytes raise FingerprintError."""
        from registration.fingerprint import compute_phash
        from core.exceptions import FingerprintError

        with pytest.raises(FingerprintError):
            compute_phash(b"not an image")


# =============================================================================
# Timestamp Tests
# =============================================================================

class TestTimestamp:
    """Test registration.timestamp.create_timestamp and verify_timestamp"""

    def test_create_with_valid_digest(self):
        """Valid SHA-256 digest produces a TimestampProof."""
        from registration.timestamp import create_timestamp

        digest = hashlib.sha256(b"test data").hexdigest()
        proof = create_timestamp(digest)

        assert proof.status in ("pending", "unverified")
        assert proof.ots_proof is not None
        assert proof.submitted_at is not None

    def test_create_with_invalid_digest_raises(self):
        """Invalid digest raises TimestampError."""
        from registration.timestamp import create_timestamp
        from core.exceptions import TimestampError

        with pytest.raises(TimestampError, match="Invalid SHA-256"):
            create_timestamp("too_short")

    def test_verify_unverified_returns_false(self):
        """Unverified local timestamps return False on verification."""
        from registration.timestamp import create_timestamp, verify_timestamp

        digest = hashlib.sha256(b"test").hexdigest()
        proof = create_timestamp(digest)

        # If it fell back to unverified, verification should return False
        if proof.status == "unverified":
            result = verify_timestamp(proof.ots_proof, digest)
            assert result is False


# =============================================================================
# Models Tests
# =============================================================================

class TestModels:
    """Test registration.models data classes."""

    def test_asset_record_to_firestore(self):
        """AssetRecord.to_firestore_dict() produces a valid dict."""
        from registration.models import AssetRecord

        record = AssetRecord(
            asset_id="test-id",
            owner_id="owner-1",
            filename="test.jpg",
            content_type="image/jpeg",
            file_size=1024,
            sha256="a" * 64,
            phash="b" * 64,
            status="registered",
        )

        data = record.to_firestore_dict()
        assert isinstance(data, dict)
        assert data["asset_id"] == "test-id"
        assert data["sha256"] == "a" * 64

    def test_register_response(self):
        """RegisterResponse serializes correctly."""
        from registration.models import RegisterResponse

        resp = RegisterResponse(
            asset_id="test-id",
            sha256="a" * 64,
            phash="b" * 64,
            status="registered",
        )

        data = resp.model_dump()
        assert data["asset_id"] == "test-id"
        assert data["status"] == "registered"

    def test_supported_content_types(self):
        """SUPPORTED_CONTENT_TYPES contains expected types."""
        from registration.models import (
            SUPPORTED_CONTENT_TYPES,
            SUPPORTED_IMAGE_TYPES,
            SUPPORTED_TEXT_TYPES,
        )

        assert "image/jpeg" in SUPPORTED_IMAGE_TYPES
        assert "image/png" in SUPPORTED_IMAGE_TYPES
        assert "text/plain" in SUPPORTED_TEXT_TYPES
        assert "application/pdf" in SUPPORTED_TEXT_TYPES
        assert SUPPORTED_CONTENT_TYPES == SUPPORTED_IMAGE_TYPES | SUPPORTED_TEXT_TYPES
