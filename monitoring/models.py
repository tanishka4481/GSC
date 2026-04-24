"""
PROVCHAIN — Monitoring Data Models
=====================================
Pydantic models for the entire monitoring pipeline (Pillar 2).

Modules:
    scanner → google_search / news_scanner / wayback
    domain_scorer → trust/risk assessment
    propagation_analyzer → 5-signal feature engine + match_decision()
    anomaly_detector → rule-based classification
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums
# =============================================================================

class ConfidenceLevel(str, Enum):
    """Match confidence levels — only match_decision() assigns these."""
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    PROBABLE_MATCH = "PROBABLE_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NO_MATCH = "NO_MATCH"


class RiskLevel(str, Enum):
    """Domain risk levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnomalyType(str, Enum):
    """Anomaly classification types from anomaly_detector."""
    VIRAL_SCRAPING = "viral_scraping"
    SYNDICATION_LEAK = "syndication_leak"
    AGGREGATOR_PATTERN = "aggregator_pattern"
    ISOLATED_COPY = "isolated_copy"
    NORMAL = "normal"


class ScanSource(str, Enum):
    """Source of a scan hit."""
    GOOGLE_WEB = "google_web"
    GOOGLE_IMAGE = "google_image"
    GOOGLE_NEWS = "google_news"
    WAYBACK = "wayback"


# =============================================================================
# Google Search Output
# =============================================================================

class SearchResult(BaseModel):
    """Raw result from a Google Custom Search query."""
    title: str = Field(..., description="Page title from search result")
    url: str = Field(..., description="Full URL of the result")
    snippet: str = Field("", description="Text snippet from search result")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail image URL (image search only)")
    source: ScanSource = Field(..., description="Which search provider returned this")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Raw API metadata")


# =============================================================================
# Wayback Machine Output
# =============================================================================

class WaybackSnapshot(BaseModel):
    """A single Wayback Machine archive snapshot."""
    url: str = Field(..., description="Original URL that was archived")
    archive_url: str = Field(..., description="Wayback Machine archive URL")
    timestamp: str = Field(..., description="Archive timestamp (YYYYMMDDHHmmss)")
    status_code: str = Field("200", description="HTTP status when archived")
    mime_type: str = Field("", description="MIME type of archived content")


# =============================================================================
# Scanner Output — Scan Hit
# =============================================================================

class ScanHit(BaseModel):
    """
    Single search result enriched with fingerprint similarity scores.

    This is the core unit of scan output — one per candidate URL found.
    """
    url: str = Field(..., description="URL where the potential copy was found")
    domain: str = Field(..., description="Extracted domain (e.g., 'example.com')")
    page_title: str = Field("", description="Page title")
    snippet: str = Field("", description="Text snippet from the page")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL if available")
    source: ScanSource = Field(..., description="Search source that found this hit")

    # Fingerprint similarity scores (separate code paths — critical rule)
    phash_similarity: Optional[float] = Field(
        None, description="pHash similarity 0-1 (images only). Null if not an image."
    )
    embedding_similarity: Optional[float] = Field(
        None, description="Gemini embedding cosine similarity 0-1. Null if embedding unavailable."
    )

    # Attribution detection
    has_attribution: Optional[bool] = Field(
        None, description="Whether the page appears to credit the original source"
    )

    discovered_at: str = Field(..., description="ISO 8601 UTC timestamp when discovered")


# =============================================================================
# Domain Scorer Output
# =============================================================================

class DomainScore(BaseModel):
    """Trust/risk assessment for a single domain."""
    domain: str = Field(..., description="The domain being scored")
    base_domain: str = Field(..., description="Base domain after subdomain stripping")
    trust_score: float = Field(..., ge=0.0, le=1.0, description="Trust score 0-1 (higher = more trusted)")
    category: str = Field("unknown", description="Domain category (news_major, social_media, etc.)")
    risk_level: RiskLevel = Field(..., description="Risk level derived from trust score")
    is_licensed: bool = Field(False, description="Whether this domain is a known licensed partner")


# =============================================================================
# Match Decision Output — from match_decision() ONLY
# =============================================================================

class MatchDecision(BaseModel):
    """
    Output of match_decision() — THE ONLY function that flags content.

    Critical rule: no other function in the codebase may assign confidence levels.
    """
    confidence: ConfidenceLevel = Field(..., description="Match confidence level")
    phash_score: Optional[float] = Field(None, description="pHash similarity used for decision")
    embedding_score: Optional[float] = Field(None, description="Embedding similarity used for decision")
    domain_risk: RiskLevel = Field(RiskLevel.HIGH, description="Domain risk level context")
    recommendation: str = Field(
        "", description="Action recommendation: 'auto_flag', 'human_review', 'log_only', 'ignore'"
    )
    reasoning: str = Field("", description="Human-readable explanation of the decision")


# =============================================================================
# Propagation Metrics — 5-signal feature vector
# =============================================================================

class PropagationMetrics(BaseModel):
    """
    Five-signal propagation feature vector.

    These signals characterize HOW content is spreading, not just WHERE.
    """
    velocity: float = Field(0.0, description="New copies per day since registration")
    entropy: float = Field(0.0, description="Shannon entropy of domain distribution")
    attribution_gap: float = Field(
        0.0, ge=0.0, le=1.0,
        description="Fraction of copies without attribution (0=all attributed, 1=none)"
    )
    total_hits: int = Field(0, description="Total number of scan hits")
    unique_domains: int = Field(0, description="Number of unique domains with copies")
    domain_risk_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of hits per risk level: {'HIGH': 3, 'MEDIUM': 1, 'LOW': 2}"
    )
    temporal_spread_hours: float = Field(
        0.0, description="Time span in hours from earliest to latest hit"
    )


# =============================================================================
# Anomaly Detection Output
# =============================================================================

class AnomalyResult(BaseModel):
    """Output of anomaly_detector — classifies the propagation pattern."""
    anomaly_type: AnomalyType = Field(..., description="Classification of the propagation pattern")
    severity: AlertSeverity = Field(..., description="Alert severity")
    explanation: str = Field("", description="Human-readable explanation of why this classification")
    contributing_factors: List[str] = Field(
        default_factory=list, description="List of signals that contributed to this classification"
    )


# =============================================================================
# Propagation Report — Full Analysis Output
# =============================================================================

class PropagationReport(BaseModel):
    """Complete propagation analysis report combining all signals."""
    asset_id: str = Field(..., description="ID of the asset being analyzed")
    scan_id: str = Field(..., description="Unique ID for this scan session")
    metrics: PropagationMetrics = Field(..., description="5-signal propagation metrics")
    match_decisions: List[MatchDecision] = Field(
        default_factory=list, description="Match decision for each scan hit"
    )
    anomaly: Optional[AnomalyResult] = Field(
        None, description="Anomaly classification result"
    )
    risk_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Composite risk score 0-1"
    )
    alert_triggered: bool = Field(False, description="Whether this report triggered an alert")
    dmca_eligible: bool = Field(
        False,
        description="Whether DMCA notice can be sent (needs HIGH_CONFIDENCE + ≥2 URLs)"
    )
    scanned_at: str = Field(..., description="ISO 8601 UTC timestamp of analysis")


# =============================================================================
# Firestore Documents
# =============================================================================

class ScanRecord(BaseModel):
    """Firestore document for 'scans' collection."""
    scan_id: str
    asset_id: str
    owner_id: str
    queries_used: List[str] = Field(default_factory=list)
    total_results: int = 0
    hits: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Optional[Dict[str, Any]] = None
    anomaly: Optional[Dict[str, Any]] = None
    risk_score: float = 0.0
    alert_triggered: bool = False
    dmca_eligible: bool = False
    status: str = "completed"
    created_at: Optional[str] = None

    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to dict suitable for Firestore .set()."""
        return self.model_dump(exclude_none=False)


class AlertRecord(BaseModel):
    """Firestore document for 'alerts' collection."""
    alert_id: str
    asset_id: str
    owner_id: str
    alert_type: str = Field(..., description="e.g., 'high_confidence_match', 'viral_scraping'")
    severity: AlertSeverity
    summary: str
    high_confidence_urls: List[str] = Field(default_factory=list)
    probable_match_urls: List[str] = Field(default_factory=list)
    anomaly_type: Optional[str] = None
    scan_id: str
    risk_score: float = 0.0
    dmca_eligible: bool = False
    created_at: Optional[str] = None
    acknowledged: bool = False

    def to_firestore_dict(self) -> Dict[str, Any]:
        """Convert to dict suitable for Firestore .set()."""
        return self.model_dump(exclude_none=False)


# =============================================================================
# API Response Models
# =============================================================================

class ScanResponse(BaseModel):
    """Response returned by POST /scan/{asset_id}."""
    scan_id: str
    asset_id: str
    total_hits: int
    high_confidence: int = 0
    probable_match: int = 0
    possible_match: int = 0
    risk_score: float = 0.0
    anomaly_type: Optional[str] = None
    alert_triggered: bool = False
    dmca_eligible: bool = False
    hits: List[Dict[str, Any]] = Field(default_factory=list)
    scanned_at: Optional[str] = None


class AlertResponse(BaseModel):
    """Response returned by GET /alerts."""
    alert_id: str
    asset_id: str
    alert_type: str
    severity: str
    summary: str
    high_confidence_count: int = 0
    probable_match_count: int = 0
    anomaly_type: Optional[str] = None
    risk_score: float = 0.0
    dmca_eligible: bool = False
    created_at: Optional[str] = None
    acknowledged: bool = False
