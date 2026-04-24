"""
PROVCHAIN — Domain Trust & Risk Scorer
========================================
Categorizes and scores domains to contextualize match decisions.

India-focused domain intelligence with built-in databases for:
    - Major Indian news outlets
    - Regional language publishers
    - Content aggregators (key targets for PROVCHAIN)
    - Social media platforms
    - Short-video platforms (ShareChat, Moj, etc.)
    - Government and educational domains
    - E-commerce platforms

Domain score flows into match_decision() as context — a HIGH_CONFIDENCE
match on ndtv.com means something very different from the same match
on an unknown scraper site.
"""

import logging
import re
from functools import lru_cache
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from monitoring.models import DomainScore, RiskLevel

logger = logging.getLogger("provchain.domain_scorer")


# =============================================================================
# Domain Trust Database (India-focused)
# =============================================================================
# Format: base_domain → (trust_score, category)
# Trust score: 0.0 (untrusted) to 1.0 (fully trusted)
# Higher trust = lower risk of being a scraper/pirate

_DOMAIN_TRUST_DB: Dict[str, Tuple[float, str]] = {
    # --- Major National News (English) ---
    "ndtv.com":                     (0.95, "news_major"),
    "thehindu.com":                 (0.95, "news_major"),
    "hindustantimes.com":           (0.95, "news_major"),
    "indianexpress.com":            (0.95, "news_major"),
    "timesofindia.indiatimes.com":  (0.95, "news_major"),
    "indiatimes.com":               (0.90, "news_major"),
    "livemint.com":                 (0.93, "news_major"),
    "firstpost.com":                (0.90, "news_major"),
    "news18.com":                   (0.90, "news_major"),
    "theprint.in":                  (0.90, "news_major"),
    "thewire.in":                   (0.88, "news_major"),
    "scroll.in":                    (0.88, "news_major"),
    "moneycontrol.com":             (0.90, "news_major"),
    "deccanherald.com":             (0.90, "news_major"),
    "deccanchronicle.com":          (0.88, "news_major"),
    "tribuneindia.com":             (0.88, "news_major"),
    "telegraphindia.com":           (0.88, "news_major"),
    "thestatesman.com":             (0.85, "news_major"),
    "newindianexpress.com":         (0.88, "news_major"),
    "outlookindia.com":             (0.88, "news_major"),
    "business-standard.com":        (0.90, "news_major"),
    "economictimes.indiatimes.com": (0.92, "news_major"),

    # --- Regional Language News ---
    "amarujala.com":        (0.85, "news_regional"),    # Hindi
    "jagran.com":           (0.85, "news_regional"),    # Hindi
    "bhaskar.com":          (0.85, "news_regional"),    # Hindi
    "navbharattimes.indiatimes.com": (0.85, "news_regional"),  # Hindi
    "livehindustan.com":    (0.85, "news_regional"),    # Hindi
    "patrika.com":          (0.83, "news_regional"),    # Hindi
    "eenadu.net":           (0.85, "news_regional"),    # Telugu
    "sakshi.com":           (0.85, "news_regional"),    # Telugu
    "andhrajyothy.com":     (0.83, "news_regional"),    # Telugu
    "manoramaonline.com":   (0.88, "news_regional"),    # Malayalam
    "mathrubhumi.com":      (0.88, "news_regional"),    # Malayalam
    "asianetnews.com":      (0.85, "news_regional"),    # Malayalam
    "dinamalar.com":        (0.85, "news_regional"),    # Tamil
    "dinamani.com":         (0.85, "news_regional"),    # Tamil
    "vikatan.com":          (0.85, "news_regional"),    # Tamil
    "anandabazar.com":      (0.88, "news_regional"),    # Bengali
    "bartamanpatrika.com":  (0.83, "news_regional"),    # Bengali
    "eisamay.com":          (0.83, "news_regional"),    # Bengali
    "loksatta.com":         (0.85, "news_regional"),    # Marathi
    "maharashtratimes.com": (0.85, "news_regional"),    # Marathi
    "divyabhaskar.co.in":   (0.85, "news_regional"),    # Gujarati
    "sandesh.com":          (0.83, "news_regional"),    # Gujarati
    "prajavani.net":        (0.85, "news_regional"),    # Kannada
    "kannadaprabha.com":    (0.83, "news_regional"),    # Kannada
    "punjabkesari.in":      (0.83, "news_regional"),    # Punjabi

    # --- Content Aggregators (KEY TARGETS for PROVCHAIN) ---
    "dailyhunt.com":        (0.40, "aggregator"),
    "dailyhunt.in":         (0.40, "aggregator"),
    "inshorts.com":         (0.45, "aggregator"),
    "newspoint.app":        (0.35, "aggregator"),
    "newsdogs.com":         (0.25, "aggregator"),
    "newsbreak.com":        (0.40, "aggregator"),
    "flipboard.com":        (0.50, "aggregator"),
    "google.com/amp":       (0.60, "aggregator"),
    "amp.dev":              (0.60, "aggregator"),

    # --- Short-Video Platforms (KEY TARGETS) ---
    "sharechat.com":        (0.35, "short_video"),
    "moj.in":               (0.30, "short_video"),
    "mojapp.in":            (0.30, "short_video"),
    "chingari.io":          (0.30, "short_video"),
    "trell.co":             (0.30, "short_video"),
    "roposo.com":           (0.30, "short_video"),
    "mitron.tv":            (0.25, "short_video"),

    # --- Global Social Media ---
    "instagram.com":        (0.70, "social_media"),
    "twitter.com":          (0.70, "social_media"),
    "x.com":                (0.70, "social_media"),
    "facebook.com":         (0.70, "social_media"),
    "fb.com":               (0.70, "social_media"),
    "linkedin.com":         (0.75, "social_media"),
    "reddit.com":           (0.65, "social_media"),
    "pinterest.com":        (0.60, "social_media"),
    "tumblr.com":           (0.55, "social_media"),
    "threads.net":          (0.70, "social_media"),

    # --- Video Platforms ---
    "youtube.com":          (0.75, "video_platform"),
    "youtu.be":             (0.75, "video_platform"),
    "vimeo.com":            (0.80, "video_platform"),
    "dailymotion.com":      (0.55, "video_platform"),
    "rumble.com":           (0.45, "video_platform"),

    # --- E-Commerce ---
    "amazon.in":            (0.60, "e_commerce"),
    "amazon.com":           (0.60, "e_commerce"),
    "flipkart.com":         (0.60, "e_commerce"),
    "snapdeal.com":         (0.55, "e_commerce"),
    "meesho.com":           (0.50, "e_commerce"),
    "myntra.com":           (0.55, "e_commerce"),

    # --- Educational ---
    "ncert.nic.in":         (0.95, "educational"),
    "cbse.gov.in":          (0.95, "educational"),
    "diksha.gov.in":        (0.95, "educational"),
    "swayam.gov.in":        (0.95, "educational"),
    "ugc.ac.in":            (0.95, "educational"),
    "aicte-india.org":      (0.90, "educational"),
    "wikipedia.org":        (0.80, "educational"),
    "britannica.com":       (0.85, "educational"),

    # --- Image/Stock ---
    "shutterstock.com":     (0.70, "stock_media"),
    "gettyimages.com":      (0.70, "stock_media"),
    "istockphoto.com":      (0.70, "stock_media"),
    "unsplash.com":         (0.75, "stock_media"),
    "pexels.com":           (0.75, "stock_media"),
    "pixabay.com":          (0.75, "stock_media"),

    # --- Blogging ---
    "medium.com":           (0.55, "blog_platform"),
    "wordpress.com":        (0.50, "blog_platform"),
    "blogger.com":          (0.45, "blog_platform"),
    "blogspot.com":         (0.45, "blog_platform"),
    "substack.com":         (0.60, "blog_platform"),
    "quora.com":            (0.55, "blog_platform"),

    # --- Known Scraper/Piracy (examples — expand as needed) ---
    "tamilrockers.com":     (0.05, "piracy"),
    "movierulz.com":        (0.05, "piracy"),
    "123movies.to":         (0.05, "piracy"),
}

# Government domain patterns (regex-based)
_GOV_PATTERNS = [
    r"\.gov\.in$",
    r"\.nic\.in$",
    r"\.ac\.in$",
    r"\.edu\.in$",
    r"\.res\.in$",
    r"\.mil\.in$",
]


# =============================================================================
# Public API
# =============================================================================

def score_domain(domain: str) -> DomainScore:
    """
    Compute trust/risk score for a domain.

    Looks up the domain in the built-in trust database. Falls back to
    pattern matching for government/educational TLDs, and defaults
    to low trust (0.20) for unknown domains.

    Args:
        domain: Full domain string (e.g., 'm.ndtv.com', 'example.com').

    Returns:
        DomainScore with trust_score, category, and risk_level.
    """
    base = _extract_base_domain(domain)

    # --- Lookup in trust database ---
    trust_score, category = _lookup_trust(base, domain)

    # --- Determine risk level ---
    risk_level = _score_to_risk(trust_score)

    result = DomainScore(
        domain=domain,
        base_domain=base,
        trust_score=trust_score,
        category=category,
        risk_level=risk_level,
        is_licensed=False,  # Placeholder — licensing check is Phase 5+
    )

    logger.debug(
        "Domain scored: %s → trust=%.2f, cat=%s, risk=%s",
        domain, trust_score, category, risk_level.value,
    )

    return result


def score_domains_batch(domains: list[str]) -> Dict[str, DomainScore]:
    """
    Score multiple domains at once. Returns {domain: DomainScore} mapping.

    Args:
        domains: List of domain strings.

    Returns:
        Dict mapping each domain to its DomainScore.
    """
    return {domain: score_domain(domain) for domain in set(domains)}


# =============================================================================
# Internal Functions
# =============================================================================

def _extract_base_domain(domain: str) -> str:
    """
    Strip subdomains to get the base/registrable domain.

    Examples:
        m.ndtv.com → ndtv.com
        hindi.news18.com → news18.com
        www.thehindu.com → thehindu.com
        navbharattimes.indiatimes.com → navbharattimes.indiatimes.com (kept: known in DB)
        sub.example.co.in → example.co.in

    This is a best-effort heuristic. For production, use the `tldextract` library.
    """
    domain = domain.lower().strip().rstrip(".")

    # Remove www. prefix
    if domain.startswith("www."):
        domain = domain[4:]

    # Check if the full domain (with subdomain) is in our database
    if domain in _DOMAIN_TRUST_DB:
        return domain

    # Handle common Indian TLDs: .co.in, .gov.in, .ac.in, .org.in, .net.in
    indian_tld_pattern = re.compile(
        r"^(?:.*\.)?([a-z0-9-]+\.(?:co|gov|ac|org|net|edu|res|mil)\.in)$"
    )
    match = indian_tld_pattern.match(domain)
    if match:
        return match.group(1)

    # Handle standard TLDs: .com, .in, .org, .net, etc.
    parts = domain.split(".")
    if len(parts) > 2:
        # Try the last two parts first
        candidate = ".".join(parts[-2:])
        if candidate in _DOMAIN_TRUST_DB:
            return candidate
        # If not in DB, return last two parts as base domain
        return candidate

    return domain


def _lookup_trust(base_domain: str, full_domain: str) -> Tuple[float, str]:
    """
    Look up trust score and category from the database.

    Priority:
    1. Exact match on base_domain in DB
    2. Government/educational TLD pattern match
    3. Default: unknown (0.20)

    Args:
        base_domain: Base domain after subdomain stripping.
        full_domain: Original full domain for pattern matching.

    Returns:
        Tuple of (trust_score, category).
    """
    # --- Direct lookup ---
    if base_domain in _DOMAIN_TRUST_DB:
        return _DOMAIN_TRUST_DB[base_domain]

    # --- Check full domain (for subdomains that are distinct entities) ---
    if full_domain in _DOMAIN_TRUST_DB:
        return _DOMAIN_TRUST_DB[full_domain]

    # --- Government/institutional pattern matching ---
    for pattern in _GOV_PATTERNS:
        if re.search(pattern, full_domain):
            return (0.95, "government")

    # --- Default: unknown ---
    return (0.20, "unknown")


def _score_to_risk(trust_score: float) -> RiskLevel:
    """
    Convert trust score to risk level.

    trust >= 0.80 → LOW risk (trusted source)
    trust >= 0.50 → MEDIUM risk (neutral / social media)
    trust <  0.50 → HIGH risk (aggregators, unknown, piracy)
    """
    if trust_score >= 0.80:
        return RiskLevel.LOW
    elif trust_score >= 0.50:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.HIGH


def extract_domain_from_url(url: str) -> str:
    """
    Extract the domain from a full URL.

    Args:
        url: Full URL (e.g., 'https://m.ndtv.com/article/12345').

    Returns:
        Domain string (e.g., 'm.ndtv.com').
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        # Remove port if present
        domain = domain.split(":")[0]
        return domain.lower()
    except Exception:
        return url.lower()
