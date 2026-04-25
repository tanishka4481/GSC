"""
PROVCHAIN — Custom Exception Hierarchy
========================================
Every module fails loudly with context. All exceptions carry:
- message: human-readable error description
- detail: dict with structured error context
- status_code: HTTP status code for API responses

Exception tree:
    ProvchainError (base)
    ├── ConfigurationError
    ├── RegistrationError
    │   ├── HashingError
    │   ├── FingerprintError
    │   └── TimestampError
    ├── MonitoringError
    │   ├── ScanError
    │   └── PropagationAnalysisError
    ├── EvidenceError
    │   ├── PDFGenerationError
    │   └── NoticeGenerationError
    ├── StorageError
    ├── AuthenticationError
    └── RateLimitError
"""

from typing import Any, Dict, Optional


# =============================================================================
# Base Exception
# =============================================================================

class ProvchainError(Exception):
    """Base exception for all PROVCHAIN errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        detail: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        self.message = message
        self.detail = detail or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize exception for JSON API responses."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "detail": self.detail,
        }


# =============================================================================
# Configuration Errors
# =============================================================================

class ConfigurationError(ProvchainError):
    """Missing environment variables, bad config values, etc."""

    def __init__(self, message: str = "Configuration error", status_code: int = 500, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)


# =============================================================================
# Registration Errors (Pillar 1)
# =============================================================================

class RegistrationError(ProvchainError):
    """Base error for asset registration failures."""

    def __init__(self, message: str = "Registration failed", status_code: int = 400, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)


class HashingError(RegistrationError):
    """SHA-256 or content normalization failed."""

    def __init__(self, message: str = "Hashing failed", **kwargs):
        super().__init__(message=message, **kwargs)


class FingerprintError(RegistrationError):
    """pHash or Gemini embedding computation failed."""

    def __init__(self, message: str = "Fingerprint generation failed", **kwargs):
        super().__init__(message=message, **kwargs)


class TimestampError(RegistrationError):
    """RFC 3161 or OpenTimestamps anchoring failed."""

    def __init__(self, message: str = "Timestamping failed", **kwargs):
        super().__init__(message=message, **kwargs)


# =============================================================================
# Monitoring Errors (Pillar 2)
# =============================================================================

class MonitoringError(ProvchainError):
    """Base error for scan/propagation failures."""

    def __init__(self, message: str = "Monitoring failed", status_code: int = 500, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)


class ScanError(MonitoringError):
    """Google Search, News, or Wayback scan failed."""

    def __init__(self, message: str = "Scan failed", **kwargs):
        super().__init__(message=message, **kwargs)


class PropagationAnalysisError(MonitoringError):
    """Feature computation or anomaly detection failed."""

    def __init__(self, message: str = "Propagation analysis failed", **kwargs):
        super().__init__(message=message, **kwargs)


# =============================================================================
# Evidence Errors (Pillar 3)
# =============================================================================

class EvidenceError(ProvchainError):
    """Base error for evidence generation failures."""

    def __init__(self, message: str = "Evidence generation failed", status_code: int = 500, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)


class PDFGenerationError(EvidenceError):
    """ReportLab PDF creation failed."""

    def __init__(self, message: str = "PDF generation failed", **kwargs):
        super().__init__(message=message, **kwargs)


class NoticeGenerationError(EvidenceError):
    """Legal notice template rendering failed."""

    def __init__(self, message: str = "Notice generation failed", **kwargs):
        super().__init__(message=message, **kwargs)


# =============================================================================
# Infrastructure Errors
# =============================================================================

class StorageError(ProvchainError):
    """Firestore or IPFS read/write failed."""

    def __init__(self, message: str = "Storage operation failed", status_code: int = 503, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)


class AuthenticationError(ProvchainError):
    """Firebase Auth token validation failed."""

    def __init__(self, message: str = "Authentication failed", status_code: int = 401, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)


class RateLimitError(ProvchainError):
    """Request rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded", status_code: int = 429, **kwargs):
        super().__init__(message=message, status_code=status_code, **kwargs)
