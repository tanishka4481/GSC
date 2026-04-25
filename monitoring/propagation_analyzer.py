"""
PROVCHAIN — Propagation Analyzer (5-Signal Feature Engine)
============================================================
Computes propagation metrics and runs match_decision() — THE ONLY
function in the entire codebase that flags content.

Five propagation signals:
    1. Velocity      — copies per day since registration
    2. Entropy       — Shannon entropy of domain distribution
    3. Attribution Gap — fraction of copies without attribution
    4. Domain Risk Distribution — breakdown of hits by risk level
    5. Temporal Spread — time span from earliest to latest hit

match_decision() combines pHash similarity, embedding similarity,
and domain risk to assign one of four confidence levels:
    HIGH_CONFIDENCE  → auto-flag (pHash > 0.92)
    PROBABLE_MATCH   → human review (embedding > 0.88)
    POSSIBLE_MATCH   → log only (both > 0.75)
    NO_MATCH         → ignore

DMCA eligibility requires: HIGH_CONFIDENCE + minimum 2 independent URLs.
"""

import logging
import math
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.exceptions import PropagationAnalysisError, StorageError
from monitoring.models import (
    AlertRecord,
    AlertSeverity,
    AnomalyResult,
    ConfidenceLevel,
    DomainScore,
    MatchDecision,
    PropagationMetrics,
    PropagationReport,
    RiskLevel,
    ScanHit,
    ScanRecord,
)

logger = logging.getLogger("provchain.propagation_analyzer")


def _get_db():
    """Get Firestore client for configured database ID."""
    from firebase_admin import firestore
    settings = get_settings()
    return firestore.client(database_id=settings.FIRESTORE_DATABASE_ID)


# =============================================================================
# match_decision() — THE ONLY function that flags content
# =============================================================================

def match_decision(
    phash_similarity: Optional[float],
    embedding_similarity: Optional[float],
    domain_score: Optional[DomainScore] = None,
) -> MatchDecision:
    """
    Determine match confidence level for a scan hit.

    *** CRITICAL RULE: This is the ONLY function that flags content. ***
    No other function in the codebase may assign confidence levels.

    Decision logic (thresholds from config.py):
        1. pHash > 0.92           → HIGH_CONFIDENCE (auto-flag)
        2. embedding > 0.88       → PROBABLE_MATCH  (human review)
        3. pHash > 0.75 AND
           embedding > 0.75       → POSSIBLE_MATCH  (log only)
        4. Otherwise              → NO_MATCH        (ignore)

    Args:
        phash_similarity: pHash similarity 0-1 (None if not an image).
        embedding_similarity: Embedding cosine similarity 0-1 (None if unavailable).
        domain_score: Domain trust/risk context (optional, for enrichment).

    Returns:
        MatchDecision with confidence level and recommendation.
    """
    settings = get_settings()
    domain_risk = domain_score.risk_level if domain_score else RiskLevel.HIGH

    # --- Decision cascade ---

    # Level 1: HIGH_CONFIDENCE (pHash pixel-level match)
    if phash_similarity is not None and phash_similarity > settings.PHASH_HIGH_CONFIDENCE:
        return MatchDecision(
            confidence=ConfidenceLevel.HIGH_CONFIDENCE,
            phash_score=phash_similarity,
            embedding_score=embedding_similarity,
            domain_risk=domain_risk,
            recommendation="auto_flag",
            reasoning=(
                f"pHash similarity {phash_similarity:.3f} exceeds HIGH_CONFIDENCE "
                f"threshold ({settings.PHASH_HIGH_CONFIDENCE}). "
                f"This is a near-identical pixel-level copy."
            ),
        )

    # Level 2: PROBABLE_MATCH (semantic embedding match)
    if embedding_similarity is not None and embedding_similarity > settings.EMBEDDING_PROBABLE_MATCH:
        return MatchDecision(
            confidence=ConfidenceLevel.PROBABLE_MATCH,
            phash_score=phash_similarity,
            embedding_score=embedding_similarity,
            domain_risk=domain_risk,
            recommendation="human_review",
            reasoning=(
                f"Embedding similarity {embedding_similarity:.3f} exceeds PROBABLE_MATCH "
                f"threshold ({settings.EMBEDDING_PROBABLE_MATCH}). "
                f"Semantically similar content — may be derivative work."
            ),
        )

    # Level 3: POSSIBLE_MATCH (both signals weak-positive)
    phash_val = phash_similarity if phash_similarity is not None else 0.0
    embed_val = embedding_similarity if embedding_similarity is not None else 0.0

    if phash_val > settings.PHASH_POSSIBLE_MATCH and embed_val > settings.EMBEDDING_POSSIBLE_MATCH:
        return MatchDecision(
            confidence=ConfidenceLevel.POSSIBLE_MATCH,
            phash_score=phash_similarity,
            embedding_score=embedding_similarity,
            domain_risk=domain_risk,
            recommendation="log_only",
            reasoning=(
                f"Both pHash ({phash_val:.3f}) and embedding ({embed_val:.3f}) "
                f"exceed POSSIBLE_MATCH thresholds "
                f"({settings.PHASH_POSSIBLE_MATCH}/{settings.EMBEDDING_POSSIBLE_MATCH}). "
                f"Moderate similarity — logged for pattern tracking."
            ),
        )

    # Level 4: NO_MATCH
    return MatchDecision(
        confidence=ConfidenceLevel.NO_MATCH,
        phash_score=phash_similarity,
        embedding_score=embedding_similarity,
        domain_risk=domain_risk,
        recommendation="ignore",
        reasoning=(
            f"Similarity scores (pHash={phash_val:.3f}, embedding={embed_val:.3f}) "
            f"below all match thresholds. No action needed."
        ),
    )


# =============================================================================
# Main Analysis Entry Point
# =============================================================================

async def analyze_propagation(
    asset_id: str,
    scan_hits: List[ScanHit],
    asset,  # AssetRecord from registration
    domain_scores: Dict[str, DomainScore],
    scan_record: ScanRecord,
) -> PropagationReport:
    """
    Run full propagation analysis on scan results.

    Pipeline:
        1. Run match_decision() on each scan hit
        2. Compute propagation metrics (5 signals)
        3. Determine composite risk score
        4. Check DMCA eligibility
        5. Determine if alert should be triggered
        6. Save scan record + create alert if needed

    Args:
        asset_id: UUID of the asset being analyzed.
        scan_hits: List of ScanHit objects from scanner.
        asset: Registered AssetRecord.
        domain_scores: Domain → DomainScore mapping.
        scan_record: ScanRecord being built.

    Returns:
        PropagationReport with all analysis results.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc).isoformat()

    logger.info("Analyzing propagation: asset_id=%s, hits=%d", asset_id, len(scan_hits))

    # --- Step 1: Run match_decision() on each hit ---
    decisions: List[MatchDecision] = []
    for hit in scan_hits:
        ds = domain_scores.get(hit.domain)
        decision = match_decision(
            phash_similarity=hit.phash_similarity,
            embedding_similarity=hit.embedding_similarity,
            domain_score=ds,
        )
        decisions.append(decision)

        logger.debug(
            "Match decision: url=%s, confidence=%s, phash=%.3f, embed=%.3f",
            hit.url,
            decision.confidence.value,
            decision.phash_score or 0,
            decision.embedding_score or 0,
        )

    # --- Step 2: Compute propagation metrics ---
    metrics = _compute_metrics(scan_hits, asset, decisions, domain_scores)

    # --- Step 3: Determine composite risk score ---
    risk_score = _determine_risk_score(metrics, decisions)

    # --- Step 4: Check DMCA eligibility ---
    high_conf_urls = [
        hit.url for hit, dec in zip(scan_hits, decisions)
        if dec.confidence == ConfidenceLevel.HIGH_CONFIDENCE
    ]
    dmca_eligible = (
        len(high_conf_urls) >= settings.DMCA_MIN_URLS
    )

    # --- Step 5: Determine alert ---
    alert_triggered = _should_trigger_alert(risk_score, decisions, settings)

    # --- Build report ---
    report = PropagationReport(
        asset_id=asset_id,
        scan_id=scan_record.scan_id,
        metrics=metrics,
        match_decisions=decisions,
        risk_score=risk_score,
        alert_triggered=alert_triggered,
        dmca_eligible=dmca_eligible,
        scanned_at=now,
    )

    # --- Step 6: Persist results ---
    # Update scan record with analysis results
    scan_record.metrics = metrics.model_dump()
    scan_record.risk_score = risk_score
    scan_record.alert_triggered = alert_triggered
    scan_record.dmca_eligible = dmca_eligible

    try:
        await _save_scan_record(scan_record)
    except Exception as e:
        logger.warning("Failed to save scan record: %s", e)

    # Create alert if triggered
    if alert_triggered:
        try:
            probable_urls = [
                hit.url for hit, dec in zip(scan_hits, decisions)
                if dec.confidence == ConfidenceLevel.PROBABLE_MATCH
            ]
            await _create_alert(
                asset_id=asset_id,
                owner_id=asset.owner_id,
                report=report,
                high_confidence_urls=high_conf_urls,
                probable_match_urls=probable_urls,
            )
        except Exception as e:
            logger.warning("Failed to create alert: %s", e)

    logger.info(
        "Analysis complete: asset_id=%s, risk=%.2f, high_conf=%d, "
        "probable=%d, dmca_eligible=%s, alert=%s",
        asset_id, risk_score, len(high_conf_urls),
        sum(1 for d in decisions if d.confidence == ConfidenceLevel.PROBABLE_MATCH),
        dmca_eligible, alert_triggered,
    )

    return report


# =============================================================================
# Propagation Metrics Computation
# =============================================================================

def _compute_metrics(
    hits: List[ScanHit],
    asset,
    decisions: List[MatchDecision],
    domain_scores: Dict[str, DomainScore],
) -> PropagationMetrics:
    """Compute all 5 propagation signals."""
    if not hits:
        return PropagationMetrics()

    velocity = _compute_velocity(hits, asset.created_at)
    entropy = _compute_entropy(hits)
    attribution_gap = _compute_attribution_gap(hits)
    unique_domains = len(set(hit.domain for hit in hits))
    domain_risk_dist = _compute_domain_risk_distribution(hits, domain_scores)
    temporal_spread = _compute_temporal_spread(hits)

    return PropagationMetrics(
        velocity=velocity,
        entropy=entropy,
        attribution_gap=attribution_gap,
        total_hits=len(hits),
        unique_domains=unique_domains,
        domain_risk_distribution=domain_risk_dist,
        temporal_spread_hours=temporal_spread,
    )


def _compute_velocity(hits: List[ScanHit], asset_created_at: Optional[str]) -> float:
    """
    Compute propagation velocity: copies per day since registration.

    velocity = total_hits / days_since_registration

    Args:
        hits: All scan hits.
        asset_created_at: ISO 8601 timestamp of asset registration.

    Returns:
        Velocity (copies per day). Returns total_hits if age < 1 day.
    """
    if not hits:
        return 0.0

    try:
        if asset_created_at:
            created = datetime.fromisoformat(asset_created_at.replace("Z", "+00:00"))
        else:
            created = datetime.now(timezone.utc)

        now = datetime.now(timezone.utc)
        days_elapsed = max((now - created).total_seconds() / 86400, 1.0)

        return round(len(hits) / days_elapsed, 2)
    except Exception:
        return float(len(hits))


def _compute_entropy(hits: List[ScanHit]) -> float:
    """
    Compute Shannon entropy of domain distribution.

    H = -Σ(p_i × log₂(p_i))

    High entropy = content spread across many domains (wide propagation)
    Low entropy = content concentrated on few domains

    Args:
        hits: All scan hits.

    Returns:
        Shannon entropy (bits). 0 for single domain, log₂(N) max for N domains.
    """
    if not hits:
        return 0.0

    domain_counts = Counter(hit.domain for hit in hits)
    total = sum(domain_counts.values())

    if total <= 1:
        return 0.0

    entropy = 0.0
    for count in domain_counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)

    return round(entropy, 4)


def _compute_attribution_gap(hits: List[ScanHit]) -> float:
    """
    Compute attribution gap: fraction of copies without attribution.

    attribution_gap = hits_without_attribution / total_hits

    0.0 = all copies give credit
    1.0 = no copies give credit (worst case)

    Args:
        hits: All scan hits.

    Returns:
        Attribution gap 0.0-1.0.
    """
    if not hits:
        return 0.0

    # Count hits where attribution was checked and found missing
    checked_hits = [h for h in hits if h.has_attribution is not None]
    if not checked_hits:
        return 0.5  # Unknown — assume moderate gap

    unattributed = sum(1 for h in checked_hits if not h.has_attribution)
    return round(unattributed / len(checked_hits), 4)


def _compute_domain_risk_distribution(
    hits: List[ScanHit],
    domain_scores: Dict[str, DomainScore],
) -> Dict[str, int]:
    """
    Count hits per domain risk level.

    Returns:
        {'HIGH': 3, 'MEDIUM': 1, 'LOW': 2}
    """
    dist: Dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for hit in hits:
        ds = domain_scores.get(hit.domain)
        risk = ds.risk_level.value if ds else "HIGH"
        dist[risk] = dist.get(risk, 0) + 1

    return dist


def _compute_temporal_spread(hits: List[ScanHit]) -> float:
    """
    Compute temporal spread in hours from earliest to latest hit.

    Args:
        hits: All scan hits.

    Returns:
        Spread in hours.
    """
    if len(hits) < 2:
        return 0.0

    try:
        timestamps = []
        for hit in hits:
            if hit.discovered_at:
                ts = datetime.fromisoformat(hit.discovered_at.replace("Z", "+00:00"))
                timestamps.append(ts)

        if len(timestamps) < 2:
            return 0.0

        spread = (max(timestamps) - min(timestamps)).total_seconds() / 3600
        return round(spread, 2)
    except Exception:
        return 0.0


# =============================================================================
# Risk Scoring
# =============================================================================

def _determine_risk_score(
    metrics: PropagationMetrics,
    decisions: List[MatchDecision],
) -> float:
    """
    Compute weighted composite risk score 0-1.

    Weights:
        - Match confidence distribution: 40%
        - Attribution gap: 25%
        - Velocity (normalized): 15%
        - Domain risk distribution: 15%
        - Entropy (normalized): 5%

    Args:
        metrics: Computed propagation metrics.
        decisions: Match decisions for each hit.

    Returns:
        Risk score 0.0 to 1.0.
    """
    if not decisions:
        return 0.0

    total = len(decisions)

    # --- Confidence score (40%) ---
    # Weight: HIGH=1.0, PROBABLE=0.7, POSSIBLE=0.3, NO_MATCH=0.0
    confidence_weights = {
        ConfidenceLevel.HIGH_CONFIDENCE: 1.0,
        ConfidenceLevel.PROBABLE_MATCH: 0.7,
        ConfidenceLevel.POSSIBLE_MATCH: 0.3,
        ConfidenceLevel.NO_MATCH: 0.0,
    }
    confidence_sum = sum(confidence_weights.get(d.confidence, 0) for d in decisions)
    confidence_score = confidence_sum / total

    # --- Attribution gap (25%) ---
    attribution_score = metrics.attribution_gap

    # --- Velocity score (15%, normalized: cap at 10 copies/day) ---
    velocity_score = min(metrics.velocity / 10.0, 1.0)

    # --- Domain risk score (15%) ---
    high_risk_ratio = metrics.domain_risk_distribution.get("HIGH", 0) / max(total, 1)
    domain_risk_score = high_risk_ratio

    # --- Entropy score (5%, normalized: cap at 3.0 bits) ---
    entropy_score = min(metrics.entropy / 3.0, 1.0)

    # --- Weighted composite ---
    risk = (
        0.40 * confidence_score
        + 0.25 * attribution_score
        + 0.15 * velocity_score
        + 0.15 * domain_risk_score
        + 0.05 * entropy_score
    )

    return round(max(0.0, min(1.0, risk)), 4)


# =============================================================================
# Alert Logic
# =============================================================================

def _should_trigger_alert(
    risk_score: float,
    decisions: List[MatchDecision],
    settings,
) -> bool:
    """
    Determine whether to trigger an alert.

    Alert triggers:
        1. risk_score > ALERT_RISK_THRESHOLD (default 0.7), OR
        2. Any HIGH_CONFIDENCE match exists

    Args:
        risk_score: Composite risk score 0-1.
        decisions: Match decisions.
        settings: App settings.

    Returns:
        True if alert should be triggered.
    """
    # Trigger on risk threshold
    if risk_score > settings.ALERT_RISK_THRESHOLD:
        return True

    # Trigger on any HIGH_CONFIDENCE match
    if any(d.confidence == ConfidenceLevel.HIGH_CONFIDENCE for d in decisions):
        return True

    return False


# =============================================================================
# Firestore Persistence
# =============================================================================

async def _save_scan_record(record: ScanRecord) -> None:
    """Write scan record to Firestore 'scans' collection."""
    try:
        db = _get_db()
        doc_ref = db.collection("scans").document(record.scan_id)
        doc_ref.set(record.to_firestore_dict())
        logger.info("Scan record saved: scan_id=%s", record.scan_id)
    except Exception as e:
        logger.warning("Firestore scan write failed: %s", e)
        raise StorageError(
            message=f"Failed to save scan record: {e}",
            detail={"scan_id": record.scan_id},
        )


async def _create_alert(
    asset_id: str,
    owner_id: str,
    report: PropagationReport,
    high_confidence_urls: List[str],
    probable_match_urls: List[str],
) -> AlertRecord:
    """Create and save an alert to Firestore 'alerts' collection."""
    alert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    # Determine alert type and severity
    if high_confidence_urls:
        alert_type = "high_confidence_match"
        severity = AlertSeverity.CRITICAL if len(high_confidence_urls) >= 3 else AlertSeverity.HIGH
    elif report.risk_score > 0.8:
        alert_type = "high_risk_propagation"
        severity = AlertSeverity.HIGH
    else:
        alert_type = "anomaly_detected"
        severity = AlertSeverity.MEDIUM

    hc_count = len(high_confidence_urls)
    pm_count = len(probable_match_urls)
    unique_domains = report.metrics.unique_domains

    summary = (
        f"{hc_count} HIGH_CONFIDENCE and {pm_count} PROBABLE_MATCH "
        f"detections across {unique_domains} domain(s). "
        f"Risk score: {report.risk_score:.2f}."
    )

    if report.dmca_eligible:
        summary += " DMCA notice eligible."

    anomaly_type_str = None
    if report.anomaly:
        anomaly_type_str = report.anomaly.anomaly_type.value

    alert = AlertRecord(
        alert_id=alert_id,
        asset_id=asset_id,
        owner_id=owner_id,
        alert_type=alert_type,
        severity=severity,
        summary=summary,
        high_confidence_urls=high_confidence_urls,
        probable_match_urls=probable_match_urls,
        anomaly_type=anomaly_type_str,
        scan_id=report.scan_id,
        risk_score=report.risk_score,
        dmca_eligible=report.dmca_eligible,
        created_at=now,
        acknowledged=False,
    )

    try:
        db = _get_db()
        doc_ref = db.collection("alerts").document(alert_id)
        doc_ref.set(alert.to_firestore_dict())
        logger.info(
            "Alert created: alert_id=%s, type=%s, severity=%s",
            alert_id, alert_type, severity.value,
        )
    except Exception as e:
        logger.warning("Firestore alert write failed: %s", e)
        raise StorageError(
            message=f"Failed to create alert: {e}",
            detail={"alert_id": alert_id},
        )

    return alert


# =============================================================================
# Firestore Read Helpers (for API routes)
# =============================================================================

def get_scan_history(asset_id: str) -> List[ScanRecord]:
    """Fetch all scan records for an asset from Firestore."""
    try:
        db = _get_db()
        query = (
            db.collection("scans")
            .where("asset_id", "==", asset_id)
            .order_by("created_at", direction="DESCENDING")
            .limit(50)
        )

        records = []
        for doc in query.stream():
            records.append(ScanRecord(**doc.to_dict()))
        return records

    except Exception as e:
        raise StorageError(
            message=f"Failed to fetch scan history: {e}",
            detail={"asset_id": asset_id},
        )


def get_alerts_for_owner(owner_id: str, acknowledged: Optional[bool] = None) -> List[AlertRecord]:
    """Fetch alerts for a publisher from Firestore."""
    try:
        db = _get_db()
        query = db.collection("alerts").where("owner_id", "==", owner_id)

        if acknowledged is not None:
            query = query.where("acknowledged", "==", acknowledged)

        query = query.order_by("created_at", direction="DESCENDING").limit(100)

        alerts = []
        for doc in query.stream():
            alerts.append(AlertRecord(**doc.to_dict()))
        return alerts

    except Exception as e:
        raise StorageError(
            message=f"Failed to fetch alerts: {e}",
            detail={"owner_id": owner_id},
        )


def acknowledge_alert(alert_id: str) -> bool:
    """Mark an alert as acknowledged in Firestore."""
    try:
        db = _get_db()
        doc_ref = db.collection("alerts").document(alert_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        doc_ref.update({
            "acknowledged": True,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info("Alert acknowledged: %s", alert_id)
        return True

    except Exception as e:
        raise StorageError(
            message=f"Failed to acknowledge alert: {e}",
            detail={"alert_id": alert_id},
        )
