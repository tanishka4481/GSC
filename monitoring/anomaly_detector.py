"""
PROVCHAIN — Anomaly Detector (Rule-Based Classification)
==========================================================
Classifies propagation patterns into anomaly types based on the
5-signal feature vector from propagation_analyzer.py.

Anomaly types:
    VIRAL_SCRAPING    — rapid spread across many HIGH-risk domains
    SYNDICATION_LEAK  — content appearing on aggregators without license
    AGGREGATOR_PATTERN — systematic aggregator crawling pattern
    ISOLATED_COPY     — single unauthorized copy on one domain
    NORMAL            — no anomalous pattern detected

This module does NOT flag content (that's match_decision()'s job).
It classifies the PATTERN of propagation to help prioritize response.
"""

import logging
from typing import List

from monitoring.models import (
    AnomalyResult,
    AnomalyType,
    AlertSeverity,
    ConfidenceLevel,
    MatchDecision,
    PropagationMetrics,
)

logger = logging.getLogger("provchain.anomaly_detector")


# =============================================================================
# Main Classification Function
# =============================================================================

def classify_anomaly(
    metrics: PropagationMetrics,
    decisions: List[MatchDecision],
) -> AnomalyResult:
    """
    Classify the propagation pattern into an anomaly type.

    Uses a rule-based decision tree over the 5-signal feature vector.
    Rules are ordered from most severe to least severe.

    Args:
        metrics: Propagation metrics (velocity, entropy, attribution gap, etc.)
        decisions: Match decisions from propagation_analyzer.

    Returns:
        AnomalyResult with classification, severity, and explanation.
    """
    factors: List[str] = []

    # Count confidence levels
    high_conf = sum(1 for d in decisions if d.confidence == ConfidenceLevel.HIGH_CONFIDENCE)
    probable = sum(1 for d in decisions if d.confidence == ConfidenceLevel.PROBABLE_MATCH)
    possible = sum(1 for d in decisions if d.confidence == ConfidenceLevel.POSSIBLE_MATCH)
    flagged = high_conf + probable

    high_risk_count = metrics.domain_risk_distribution.get("HIGH", 0)

    # =========================================================================
    # Rule 1: VIRAL_SCRAPING
    # =========================================================================
    # High velocity + high entropy + mostly high-risk domains
    # Pattern: content scraped and re-posted rapidly across many sketchy sites
    if (
        metrics.velocity >= 3.0
        and metrics.entropy >= 1.5
        and metrics.unique_domains >= 3
        and high_risk_count >= 2
        and flagged >= 2
    ):
        factors.extend([
            f"Velocity {metrics.velocity:.1f} copies/day (threshold: 3.0)",
            f"Entropy {metrics.entropy:.2f} bits (threshold: 1.5)",
            f"{metrics.unique_domains} unique domains",
            f"{high_risk_count} HIGH-risk domains",
            f"{flagged} flagged matches (HIGH/PROBABLE)",
        ])

        return AnomalyResult(
            anomaly_type=AnomalyType.VIRAL_SCRAPING,
            severity=AlertSeverity.CRITICAL,
            explanation=(
                "Viral scraping pattern detected: content is being rapidly copied "
                f"across {metrics.unique_domains} domains at {metrics.velocity:.1f} "
                f"copies/day, primarily on high-risk domains. "
                f"Immediate action recommended."
            ),
            contributing_factors=factors,
        )

    # =========================================================================
    # Rule 2: SYNDICATION_LEAK
    # =========================================================================
    # Content on aggregators without attribution
    # Pattern: Dailyhunt/Inshorts/etc. picked up content without license
    aggregator_hits = metrics.domain_risk_distribution.get("HIGH", 0)
    if (
        metrics.attribution_gap >= 0.7
        and aggregator_hits >= 1
        and flagged >= 1
        and metrics.total_hits >= 2
    ):
        factors.extend([
            f"Attribution gap {metrics.attribution_gap:.0%} (threshold: 70%)",
            f"{aggregator_hits} hits on high-risk/aggregator domains",
            f"{flagged} flagged matches",
        ])

        return AnomalyResult(
            anomaly_type=AnomalyType.SYNDICATION_LEAK,
            severity=AlertSeverity.HIGH,
            explanation=(
                "Syndication leak detected: content appearing on aggregator/high-risk "
                f"platforms without attribution ({metrics.attribution_gap:.0%} attribution gap). "
                f"This may indicate unauthorized syndication or content scraping."
            ),
            contributing_factors=factors,
        )

    # =========================================================================
    # Rule 3: AGGREGATOR_PATTERN
    # =========================================================================
    # Low entropy (few domains) but systematic — typical of automated crawlers
    if (
        metrics.entropy < 1.0
        and metrics.total_hits >= 3
        and metrics.unique_domains <= 2
        and flagged >= 1
    ):
        factors.extend([
            f"Low entropy {metrics.entropy:.2f} (threshold: <1.0)",
            f"{metrics.total_hits} hits on only {metrics.unique_domains} domain(s)",
            "Concentrated pattern suggests automated crawling",
        ])

        return AnomalyResult(
            anomaly_type=AnomalyType.AGGREGATOR_PATTERN,
            severity=AlertSeverity.MEDIUM,
            explanation=(
                f"Aggregator pattern detected: {metrics.total_hits} copies "
                f"concentrated on {metrics.unique_domains} domain(s). "
                f"Low entropy ({metrics.entropy:.2f}) suggests systematic crawling "
                f"rather than organic sharing."
            ),
            contributing_factors=factors,
        )

    # =========================================================================
    # Rule 4: ISOLATED_COPY
    # =========================================================================
    # Single high-confidence copy on one domain
    if high_conf >= 1 and metrics.unique_domains <= 1:
        factors.extend([
            f"{high_conf} HIGH_CONFIDENCE match(es)",
            f"Single domain ({metrics.unique_domains})",
            "Isolated unauthorized copy",
        ])

        return AnomalyResult(
            anomaly_type=AnomalyType.ISOLATED_COPY,
            severity=AlertSeverity.MEDIUM,
            explanation=(
                f"Isolated copy detected: {high_conf} high-confidence match(es) "
                f"found on a single domain. This appears to be an individual "
                f"unauthorized reproduction rather than a systematic pattern."
            ),
            contributing_factors=factors,
        )

    # =========================================================================
    # Rule 5: NORMAL
    # =========================================================================
    # No significant anomaly detected
    if flagged > 0:
        factors.append(f"{flagged} matches found but pattern is not anomalous")
    else:
        factors.append("No significant matches detected")

    return AnomalyResult(
        anomaly_type=AnomalyType.NORMAL,
        severity=AlertSeverity.LOW,
        explanation=(
            "No anomalous propagation pattern detected. "
            f"Metrics: velocity={metrics.velocity:.1f}/day, "
            f"entropy={metrics.entropy:.2f}, "
            f"attribution_gap={metrics.attribution_gap:.0%}, "
            f"hits={metrics.total_hits}."
        ),
        contributing_factors=factors,
    )
