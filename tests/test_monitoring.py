"""
Tests for Phase 3 Propagation Monitoring
"""

import pytest
import math
from unittest.mock import patch, MagicMock

from monitoring.models import (
    ScanHit,
    DomainScore,
    ScanSource,
    ConfidenceLevel,
    RiskLevel,
    MatchDecision,
    AnomalyType,
    AlertSeverity,
    PropagationMetrics,
)
from monitoring.domain_scorer import score_domain, _extract_base_domain
from monitoring.propagation_analyzer import (
    match_decision,
    _compute_metrics,
    _determine_risk_score,
)
from monitoring.scanner import _build_search_queries
from monitoring.anomaly_detector import classify_anomaly


# =============================================================================
# Domain Scorer Tests
# =============================================================================

def test_extract_base_domain():
    assert _extract_base_domain("m.ndtv.com") == "ndtv.com"
    assert _extract_base_domain("hindi.news18.com") == "news18.com"
    assert _extract_base_domain("www.thehindu.com") == "thehindu.com"
    assert _extract_base_domain("navbharattimes.indiatimes.com") == "navbharattimes.indiatimes.com"
    assert _extract_base_domain("sub.example.co.in") == "example.co.in"
    assert _extract_base_domain("example.com") == "example.com"


def test_score_domain():
    # Trusted news
    score1 = score_domain("www.ndtv.com")
    assert score1.trust_score == 0.95
    assert score1.risk_level == RiskLevel.LOW
    assert score1.category == "news_major"

    # Aggregator (High risk)
    score2 = score_domain("dailyhunt.in")
    assert score2.trust_score == 0.40
    assert score2.risk_level == RiskLevel.HIGH
    assert score2.category == "aggregator"

    # Government
    score3 = score_domain("uidai.gov.in")
    assert score3.trust_score == 0.95
    assert score3.risk_level == RiskLevel.LOW
    assert score3.category == "government"

    # Unknown
    score4 = score_domain("some-random-site.xyz")
    assert score4.trust_score == 0.20
    assert score4.risk_level == RiskLevel.HIGH
    assert score4.category == "unknown"


# =============================================================================
# Propagation Analyzer Tests
# =============================================================================

def test_match_decision_high_confidence():
    ds = DomainScore(
        domain="example.com", base_domain="example.com", 
        trust_score=0.2, category="unknown", risk_level=RiskLevel.HIGH
    )
    # pHash > 0.92
    decision = match_decision(phash_similarity=0.95, embedding_similarity=0.80, domain_score=ds)
    assert decision.confidence == ConfidenceLevel.HIGH_CONFIDENCE
    assert decision.recommendation == "auto_flag"


def test_match_decision_probable_match():
    ds = DomainScore(
        domain="example.com", base_domain="example.com", 
        trust_score=0.2, category="unknown", risk_level=RiskLevel.HIGH
    )
    # embedding > 0.88, pHash weak
    decision = match_decision(phash_similarity=0.5, embedding_similarity=0.90, domain_score=ds)
    assert decision.confidence == ConfidenceLevel.PROBABLE_MATCH
    assert decision.recommendation == "human_review"


def test_match_decision_possible_match():
    ds = DomainScore(
        domain="example.com", base_domain="example.com", 
        trust_score=0.2, category="unknown", risk_level=RiskLevel.HIGH
    )
    # Both > 0.75
    decision = match_decision(phash_similarity=0.80, embedding_similarity=0.85, domain_score=ds)
    assert decision.confidence == ConfidenceLevel.POSSIBLE_MATCH
    assert decision.recommendation == "log_only"


def test_match_decision_no_match():
    ds = DomainScore(
        domain="example.com", base_domain="example.com", 
        trust_score=0.2, category="unknown", risk_level=RiskLevel.HIGH
    )
    # Both < 0.75
    decision = match_decision(phash_similarity=0.40, embedding_similarity=0.60, domain_score=ds)
    assert decision.confidence == ConfidenceLevel.NO_MATCH
    assert decision.recommendation == "ignore"


def test_compute_metrics():
    # Create mock hits
    hits = [
        ScanHit(
            url="http://site1.com/1", domain="site1.com", source=ScanSource.GOOGLE_WEB,
            phash_similarity=0.9, embedding_similarity=0.9, has_attribution=False,
            discovered_at="2026-04-24T00:00:00Z"
        ),
        ScanHit(
            url="http://site2.com/1", domain="site2.com", source=ScanSource.GOOGLE_WEB,
            phash_similarity=0.9, embedding_similarity=0.9, has_attribution=False,
            discovered_at="2026-04-24T01:00:00Z"
        ),
        ScanHit(
            url="http://site3.com/1", domain="site3.com", source=ScanSource.GOOGLE_WEB,
            phash_similarity=0.9, embedding_similarity=0.9, has_attribution=True,
            discovered_at="2026-04-24T02:00:00Z"
        ),
    ]

    class MockAsset:
        created_at = "2026-04-23T00:00:00Z"

    domain_scores = {
        "site1.com": DomainScore(domain="site1.com", base_domain="site1.com", trust_score=0.2, risk_level=RiskLevel.HIGH),
        "site2.com": DomainScore(domain="site2.com", base_domain="site2.com", trust_score=0.2, risk_level=RiskLevel.HIGH),
        "site3.com": DomainScore(domain="site3.com", base_domain="site3.com", trust_score=0.9, risk_level=RiskLevel.LOW),
    }

    decisions = [
        MatchDecision(confidence=ConfidenceLevel.HIGH_CONFIDENCE, domain_risk=RiskLevel.HIGH),
        MatchDecision(confidence=ConfidenceLevel.HIGH_CONFIDENCE, domain_risk=RiskLevel.HIGH),
        MatchDecision(confidence=ConfidenceLevel.HIGH_CONFIDENCE, domain_risk=RiskLevel.LOW),
    ]

    metrics = _compute_metrics(hits, MockAsset(), decisions, domain_scores)
    
    assert metrics.total_hits == 3
    assert metrics.unique_domains == 3
    # 2 hits have no attribution out of 3 total -> attribution gap should be ~0.6667
    assert math.isclose(metrics.attribution_gap, 0.6667, rel_tol=1e-3)
    # Entropy of [1/3, 1/3, 1/3] = ~1.58
    assert math.isclose(metrics.entropy, 1.58, rel_tol=1e-2)
    assert metrics.domain_risk_distribution["HIGH"] == 2
    assert metrics.domain_risk_distribution["LOW"] == 1
    # Temporal spread = 2 hours
    assert metrics.temporal_spread_hours == 2.0


# =============================================================================
# Anomaly Detector Tests
# =============================================================================

def test_classify_anomaly_viral_scraping():
    metrics = PropagationMetrics(
        velocity=5.0,
        entropy=2.0,
        attribution_gap=0.9,
        total_hits=10,
        unique_domains=5,
        domain_risk_distribution={"HIGH": 8, "MEDIUM": 2, "LOW": 0},
        temporal_spread_hours=24.0,
    )
    decisions = [
        MatchDecision(confidence=ConfidenceLevel.HIGH_CONFIDENCE, domain_risk=RiskLevel.HIGH),
        MatchDecision(confidence=ConfidenceLevel.PROBABLE_MATCH, domain_risk=RiskLevel.HIGH),
    ]

    anomaly = classify_anomaly(metrics, decisions)
    assert anomaly.anomaly_type == AnomalyType.VIRAL_SCRAPING
    assert anomaly.severity == AlertSeverity.CRITICAL


def test_classify_anomaly_syndication_leak():
    metrics = PropagationMetrics(
        velocity=1.0,
        entropy=1.0,
        attribution_gap=0.8,
        total_hits=3,
        unique_domains=2,
        domain_risk_distribution={"HIGH": 3},
        temporal_spread_hours=24.0,
    )
    decisions = [
        MatchDecision(confidence=ConfidenceLevel.PROBABLE_MATCH, domain_risk=RiskLevel.HIGH),
    ]

    anomaly = classify_anomaly(metrics, decisions)
    assert anomaly.anomaly_type == AnomalyType.SYNDICATION_LEAK
    assert anomaly.severity == AlertSeverity.HIGH


def test_classify_anomaly_aggregator_pattern():
    metrics = PropagationMetrics(
        velocity=1.0,
        entropy=0.5,
        attribution_gap=0.5,
        total_hits=5,
        unique_domains=1,
        domain_risk_distribution={"HIGH": 5},
        temporal_spread_hours=24.0,
    )
    decisions = [
        MatchDecision(confidence=ConfidenceLevel.PROBABLE_MATCH, domain_risk=RiskLevel.HIGH),
    ]

    anomaly = classify_anomaly(metrics, decisions)
    assert anomaly.anomaly_type == AnomalyType.AGGREGATOR_PATTERN
    assert anomaly.severity == AlertSeverity.MEDIUM


def test_classify_anomaly_isolated_copy():
    metrics = PropagationMetrics(
        velocity=0.1,
        entropy=0.0,
        attribution_gap=1.0,
        total_hits=1,
        unique_domains=1,
        domain_risk_distribution={"HIGH": 1},
        temporal_spread_hours=0.0,
    )
    decisions = [
        MatchDecision(confidence=ConfidenceLevel.HIGH_CONFIDENCE, domain_risk=RiskLevel.HIGH),
    ]

    anomaly = classify_anomaly(metrics, decisions)
    assert anomaly.anomaly_type == AnomalyType.ISOLATED_COPY
    assert anomaly.severity == AlertSeverity.MEDIUM


def test_classify_anomaly_normal():
    metrics = PropagationMetrics(
        velocity=0.1,
        entropy=1.0,
        attribution_gap=0.0,
        total_hits=2,
        unique_domains=2,
        domain_risk_distribution={"LOW": 2},
        temporal_spread_hours=48.0,
    )
    decisions = [
        MatchDecision(confidence=ConfidenceLevel.POSSIBLE_MATCH, domain_risk=RiskLevel.LOW),
        MatchDecision(confidence=ConfidenceLevel.NO_MATCH, domain_risk=RiskLevel.LOW),
    ]

    anomaly = classify_anomaly(metrics, decisions)
    assert anomaly.anomaly_type == AnomalyType.NORMAL
    assert anomaly.severity == AlertSeverity.LOW


@pytest.mark.asyncio
async def test_build_search_queries_uses_content_summary_for_images():
    from registration.models import AssetRecord

    asset = AssetRecord(
        asset_id="asset-1",
        owner_id="owner-1",
        filename="dog.jpg",
        content_type="image/jpeg",
        file_size=1234,
        sha256="a" * 64,
        content_summary="mona lisa portrait painting",
    )

    settings = type("Settings", (), {"SCAN_IMAGE_DOWNLOAD_TIMEOUT": 10.0})()
    queries = await _build_search_queries(asset, settings)

    assert queries[0] == ("mona lisa portrait painting", "image")
    assert queries[1] == ('"mona lisa portrait painting"', "web")
    assert all("dog" not in query for query, _ in queries)


@pytest.mark.asyncio
async def test_build_search_queries_uses_content_summary_for_text_assets():
    from registration.models import AssetRecord

    asset = AssetRecord(
        asset_id="asset-2",
        owner_id="owner-2",
        filename="random-name.pdf",
        content_type="application/pdf",
        file_size=4321,
        sha256="b" * 64,
        content_summary="quantum entanglement graph neural networks",
    )

    settings = type("Settings", (), {"SCAN_IMAGE_DOWNLOAD_TIMEOUT": 10.0})()
    queries = await _build_search_queries(asset, settings)

    assert queries[0] == ("quantum entanglement graph neural networks", "web")
    assert queries[1] == ("quantum entanglement graph neural networks", "news")
    assert all("random-name" not in query for query, _ in queries)
