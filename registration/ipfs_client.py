"""
PROVCHAIN — IPFS Pinning via Pinata
=====================================
Stores original files on IPFS for tamper-proof, decentralized archival.

IPFS addresses files by content hash (CID) — if the content changes,
the CID changes. This makes IPFS inherently tamper-evident.

Pinata is a managed IPFS pinning service that keeps files available
on the network. We use their REST API with JWT authentication.

If PINATA_JWT is not configured, IPFS pinning is skipped gracefully.
"""

import json
import logging
from datetime import datetime, timezone

import httpx

from core.config import get_settings
from core.exceptions import StorageError
from registration.models import IPFSResult

logger = logging.getLogger("provchain.ipfs")


async def pin_to_ipfs(
    file_bytes: bytes,
    filename: str,
    metadata: dict | None = None,
) -> IPFSResult | None:
    """
    Pin a file to IPFS via Pinata's pinFileToIPFS endpoint.

    The file is uploaded to Pinata, which pins it on the IPFS network.
    Returns an IPFSResult with the CID (content identifier) that can
    be used to retrieve the file from any IPFS gateway.

    Args:
        file_bytes: Raw file bytes to pin.
        filename: Original filename (stored as Pinata metadata).
        metadata: Optional dict of key-value pairs for Pinata metadata.

    Returns:
        IPFSResult with cid, pin_size, and timestamp.
        None if PINATA_JWT is not configured (graceful skip).

    Raises:
        StorageError: If the Pinata API returns an error.
    """
    settings = get_settings()

    if not settings.PINATA_JWT:
        logger.warning(
            "PINATA_JWT not configured — skipping IPFS pinning. "
            "Set PINATA_JWT in .env to enable IPFS archival."
        )
        return None

    try:
        url = f"{settings.PINATA_API_URL}/pinning/pinFileToIPFS"

        # Build Pinata metadata
        pinata_metadata = {
            "name": filename,
            "keyvalues": metadata or {},
        }

        # Build the multipart form data
        # Pinata expects: file, pinataMetadata, pinataOptions
        files = {
            "file": (filename, file_bytes),
        }
        data = {
            "pinataMetadata": json.dumps(pinata_metadata),
            "pinataOptions": json.dumps({"cidVersion": 1}),
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.PINATA_JWT}",
                },
                files=files,
                data=data,
            )

        if response.status_code != 200:
            raise StorageError(
                message=f"Pinata API error: {response.status_code}",
                detail={
                    "status_code": response.status_code,
                    "response": response.text[:500],
                },
            )

        result = response.json()
        cid = result.get("IpfsHash", "")
        pin_size = result.get("PinSize", 0)

        logger.info(
            "File pinned to IPFS: cid=%s, size=%d bytes, filename=%s",
            cid,
            pin_size,
            filename,
        )

        return IPFSResult(
            cid=cid,
            pin_size=pin_size,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except StorageError:
        raise
    except Exception as e:
        raise StorageError(
            message=f"IPFS pinning failed: {e}",
            detail={"filename": filename, "file_size": len(file_bytes)},
        )


def get_ipfs_url(cid: str) -> str:
    """
    Construct the public IPFS gateway URL for a given CID.

    Args:
        cid: IPFS content identifier.

    Returns:
        Full gateway URL string.
    """
    return f"https://gateway.pinata.cloud/ipfs/{cid}"


async def unpin_from_ipfs(cid: str) -> bool:
    """
    Unpin a file from Pinata (removes it from their IPFS pinning).

    Note: The file may still be available on the IPFS network if
    other nodes have cached or pinned it.

    Args:
        cid: IPFS content identifier to unpin.

    Returns:
        True if successfully unpinned, False otherwise.

    Raises:
        StorageError: If the Pinata API returns an error.
    """
    settings = get_settings()

    if not settings.PINATA_JWT:
        logger.warning("PINATA_JWT not configured — cannot unpin")
        return False

    try:
        url = f"{settings.PINATA_API_URL}/pinning/unpin/{cid}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                url,
                headers={
                    "Authorization": f"Bearer {settings.PINATA_JWT}",
                },
            )

        if response.status_code == 200:
            logger.info("Unpinned from IPFS: cid=%s", cid)
            return True
        else:
            logger.warning(
                "Unpin failed: cid=%s, status=%d", cid, response.status_code
            )
            return False

    except Exception as e:
        raise StorageError(
            message=f"IPFS unpin failed: {e}",
            detail={"cid": cid},
        )
