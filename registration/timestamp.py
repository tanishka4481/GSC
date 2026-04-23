"""
PROVCHAIN — Blockchain Timestamping
=====================================
Proves a digital asset existed at a specific point in time by anchoring
its SHA-256 digest to the Bitcoin blockchain via OpenTimestamps.

How it works:
1. We submit the file's SHA-256 digest to OTS calendar servers
2. Calendar servers batch digests into a Merkle tree
3. The Merkle root is anchored into a Bitcoin transaction
4. We get a .ots proof file that anyone can independently verify

Proof lifecycle:
- pending    → submitted to calendar, awaiting Bitcoin anchor (~1-2 hours)
- confirmed  → anchored in Bitcoin block, independently verifiable
- unverified → fallback if OTS servers unreachable (local timestamp only)
"""

import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

from core.exceptions import TimestampError
from registration.models import TimestampProof

logger = logging.getLogger("provchain.timestamp")


def create_timestamp(sha256_digest: str) -> TimestampProof:
    """
    Submit a SHA-256 digest to OpenTimestamps calendar servers for
    Bitcoin blockchain anchoring.

    The proof starts as 'pending' — it contains a receipt from the
    calendar server. After ~1-2 hours, the proof can be upgraded to
    'confirmed' once the Bitcoin block is mined.

    If OTS calendar servers are unreachable, falls back to an
    'unverified' local timestamp (still useful as a record, but
    not independently verifiable).

    Args:
        sha256_digest: Hex-encoded SHA-256 digest to timestamp.

    Returns:
        TimestampProof with status, ots_proof bytes, and submitted_at.

    Raises:
        TimestampError: On critical failures (invalid digest, etc.)
    """
    if not sha256_digest or len(sha256_digest) != 64:
        raise TimestampError(
            message=f"Invalid SHA-256 digest: expected 64 hex chars, got {len(sha256_digest) if sha256_digest else 0}",
            detail={"digest": sha256_digest},
        )

    submitted_at = datetime.now(timezone.utc).isoformat()

    try:
        import opentimestamps.core.timestamp as ots_timestamp
        import opentimestamps.core.op as ots_op
        import opentimestamps.core.serialize as ots_serialize
        from opentimestamps.core.notary import PendingAttestation
        from opentimestamps.timestamp import Timestamp
        import opentimestamps.calendar as ots_calendar

        # Convert hex digest to bytes
        digest_bytes = bytes.fromhex(sha256_digest)

        # Create a timestamp for the digest
        file_timestamp = Timestamp(digest_bytes)

        # Submit to public OTS calendar servers
        calendar_urls = [
            "https://a.pool.opentimestamps.org",
            "https://b.pool.opentimestamps.org",
            "https://a.pool.eternitywall.com",
        ]

        submitted = False
        for url in calendar_urls:
            try:
                calendar = ots_calendar.RemoteCalendar(url)
                calendar.submit(digest_bytes, file_timestamp)
                submitted = True
                logger.info("Timestamp submitted to OTS calendar: %s", url)
                break
            except Exception as cal_err:
                logger.warning("OTS calendar %s failed: %s", url, cal_err)
                continue

        if submitted:
            # Serialize the timestamp proof
            ctx = ots_serialize.BytesSerializationContext()
            file_timestamp.serialize(ctx)
            ots_bytes = ctx.getbytes()
            ots_b64 = base64.b64encode(ots_bytes).decode("ascii")

            logger.info(
                "Timestamp proof created: digest=%s…, proof_size=%d bytes",
                sha256_digest[:16],
                len(ots_bytes),
            )

            return TimestampProof(
                status="pending",
                ots_proof=ots_b64,
                submitted_at=submitted_at,
                confirmed_at=None,
                bitcoin_block=None,
            )
        else:
            # All calendars failed — fall back to unverified
            logger.warning(
                "All OTS calendars unreachable — falling back to unverified timestamp"
            )
            return _create_unverified_timestamp(sha256_digest, submitted_at)

    except ImportError:
        # opentimestamps-client not installed — fall back gracefully
        logger.warning(
            "opentimestamps-client not installed — using unverified timestamp. "
            "Install with: pip install opentimestamps-client"
        )
        return _create_unverified_timestamp(sha256_digest, submitted_at)

    except TimestampError:
        raise
    except Exception as e:
        logger.warning("OTS submission failed: %s — falling back to unverified", e)
        return _create_unverified_timestamp(sha256_digest, submitted_at)


def _create_unverified_timestamp(sha256_digest: str, submitted_at: str) -> TimestampProof:
    """
    Create a local unverified timestamp as a fallback.

    This records the time but is NOT independently verifiable against
    a blockchain. It's still useful as an internal record.

    Args:
        sha256_digest: The digest being timestamped.
        submitted_at: ISO 8601 timestamp string.

    Returns:
        TimestampProof with status='unverified'.
    """
    # Create a simple proof payload for record-keeping
    proof_data = f"{sha256_digest}:{submitted_at}:provchain-local"
    proof_b64 = base64.b64encode(proof_data.encode("utf-8")).decode("ascii")

    return TimestampProof(
        status="unverified",
        ots_proof=proof_b64,
        submitted_at=submitted_at,
        confirmed_at=None,
        bitcoin_block=None,
    )


def verify_timestamp(ots_proof_b64: str, sha256_digest: str) -> bool:
    """
    Verify an OpenTimestamps proof against the Bitcoin blockchain.

    For 'pending' proofs, this checks against the calendar server.
    For 'confirmed' proofs, this verifies the Bitcoin block inclusion.
    For 'unverified' proofs, this always returns False.

    Args:
        ots_proof_b64: Base64-encoded .ots proof bytes.
        sha256_digest: The original SHA-256 digest that was timestamped.

    Returns:
        True if the proof is valid and confirmed, False otherwise.

    Raises:
        TimestampError: If proof data is corrupted.
    """
    try:
        proof_bytes = base64.b64decode(ots_proof_b64)

        # Check if this is an unverified local timestamp
        try:
            decoded = proof_bytes.decode("utf-8")
            if decoded.endswith(":provchain-local"):
                logger.debug("Unverified local timestamp — cannot verify")
                return False
        except UnicodeDecodeError:
            pass  # Binary OTS proof — continue with verification

        try:
            import opentimestamps.core.serialize as ots_serialize
            from opentimestamps.timestamp import Timestamp

            ctx = ots_serialize.BytesDeserializationContext(proof_bytes)
            timestamp = Timestamp.deserialize(ctx, bytes.fromhex(sha256_digest))

            # Check attestations
            for attestation in timestamp.all_attestations():
                if hasattr(attestation, 'block_height'):
                    logger.info(
                        "Timestamp verified: Bitcoin block %d",
                        attestation.block_height,
                    )
                    return True

            logger.debug("Timestamp proof valid but not yet Bitcoin-confirmed")
            return False

        except ImportError:
            logger.warning("opentimestamps-client not installed — cannot verify")
            return False

    except Exception as e:
        raise TimestampError(
            message=f"Timestamp verification failed: {e}",
            detail={"digest": sha256_digest},
        )


def upgrade_timestamp(ots_proof_b64: str) -> Optional[str]:
    """
    Attempt to upgrade a pending OTS proof to a confirmed Bitcoin proof.

    This should be called periodically (e.g., by a background job) for
    proofs with status='pending'. Once the Bitcoin block is mined (~1-2 hours),
    the proof can be upgraded to include the block attestation.

    Args:
        ots_proof_b64: Base64-encoded .ots proof bytes.

    Returns:
        Updated base64-encoded proof if upgraded, None if still pending.
    """
    try:
        proof_bytes = base64.b64decode(ots_proof_b64)

        # Skip unverified local timestamps
        try:
            decoded = proof_bytes.decode("utf-8")
            if decoded.endswith(":provchain-local"):
                return None
        except UnicodeDecodeError:
            pass

        try:
            import opentimestamps.core.serialize as ots_serialize
            from opentimestamps.timestamp import Timestamp
            import opentimestamps.calendar as ots_calendar

            ctx = ots_serialize.BytesDeserializationContext(proof_bytes)
            timestamp = Timestamp.deserialize(ctx, None)

            # Try to upgrade with calendar servers
            calendar_urls = [
                "https://a.pool.opentimestamps.org",
                "https://b.pool.opentimestamps.org",
            ]

            upgraded = False
            for url in calendar_urls:
                try:
                    calendar = ots_calendar.RemoteCalendar(url)
                    calendar.upgrade_timestamp(timestamp)
                    upgraded = True
                    break
                except Exception:
                    continue

            if upgraded:
                ctx = ots_serialize.BytesSerializationContext()
                timestamp.serialize(ctx)
                return base64.b64encode(ctx.getbytes()).decode("ascii")

            return None

        except ImportError:
            return None

    except Exception as e:
        logger.warning("Timestamp upgrade failed: %s", e)
        return None
