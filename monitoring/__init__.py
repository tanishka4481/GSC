# monitoring module — Pillar 2: Propagation Monitor
# Pipeline: scanner → domain_scorer → propagation_analyzer → anomaly_detector
#
# Search providers: google_search, wayback
# Analysis: domain_scorer, propagation_analyzer, anomaly_detector

from monitoring.scanner import scan_asset
from monitoring.propagation_analyzer import (
    analyze_propagation,
    match_decision,
    get_scan_history,
    get_alerts_for_owner,
    acknowledge_alert,
)
from monitoring.domain_scorer import score_domain, score_domains_batch
from monitoring.anomaly_detector import classify_anomaly
from monitoring.google_search import get_quota_status
from monitoring.models import (
    ConfidenceLevel,
    RiskLevel,
    AlertSeverity,
    AnomalyType,
    ScanHit,
    DomainScore,
    MatchDecision,
    PropagationMetrics,
    PropagationReport,
    ScanRecord,
    AlertRecord,
    ScanResponse,
    AlertResponse,
)

__all__ = [
    # Orchestration
    "scan_asset",
    "analyze_propagation",
    "classify_anomaly",
    # Decision (critical rule: ONLY function that flags)
    "match_decision",
    # Scoring
    "score_domain",
    "score_domains_batch",
    # Firestore helpers
    "get_scan_history",
    "get_alerts_for_owner",
    "acknowledge_alert",
    # Quota
    "get_quota_status",
    # Enums
    "ConfidenceLevel",
    "RiskLevel",
    "AlertSeverity",
    "AnomalyType",
    # Models
    "ScanHit",
    "DomainScore",
    "MatchDecision",
    "PropagationMetrics",
    "PropagationReport",
    "ScanRecord",
    "AlertRecord",
    "ScanResponse",
    "AlertResponse",
]
