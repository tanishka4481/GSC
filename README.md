# PROVCHAIN
### Unified Digital Asset Intelligence Platform for Indian Publishers

> **"Content ID for everyone — not just the top 0.1%."**

---

## Table of Contents
1. [Problem Statement](#problem-statement)
2. [Target Users](#target-users)
3. [Legal Framework (India)](#legal-framework-india)
4. [System Architecture](#system-architecture)
5. [Three Pillars](#three-pillars)
6. [Tech Stack](#tech-stack)
7. [Project Structure](#project-structure)
8. [Module Breakdown](#module-breakdown)
9. [Data Flow](#data-flow)
10. [API Reference](#api-reference)
11. [Evidence Bundle Spec](#evidence-bundle-spec)
12. [Deployment](#deployment)
13. [Cost Model](#cost-model)
14. [Roadmap](#roadmap)

---

## Problem Statement

Regional news agencies, educational institutions, and independent publishers in India lose
attribution, revenue, and legal control over their digital assets the moment they publish.
Content is scraped, reposted, and redistributed across platforms like ShareChat, Moj,
Dailyhunt, YouTube, and regional news aggregators — without credit, payment, or permission.

Enterprise-grade content protection (Nielsen, Audible Magic, YouTube ContentID) is
inaccessible to Indian publishers by cost and infrastructure. A regional Marathi newspaper
or a CBSE coaching institute has no actionable recourse.

**PROVCHAIN bridges that gap**: register assets with legally defensible timestamps under
the Indian Copyright Act, 1957 — detect propagation anomalies that signal scraping vs
legitimate sharing — and convert every detection into a one-click legal notice, turning
a process that takes a legal team weeks into a workflow that takes five minutes.

---

## Target Users

| Segment | Pain Point | Volume |
|---|---|---|
| **Regional news agencies** | Articles and photos scraped by Dailyhunt, aggregators without credit | High |
| **Educational content boards** | NCERT, CBSE, coaching institute material redistributed illegally | High |
| **Independent media houses** | Visual and written content misappropriated at scale | Medium |
| **Independent creators** | Expansion market — not primary user at launch | Low |

**Primary Geography:** Tier-1 and Tier-2 Indian cities. Language coverage: Hindi, Tamil,
Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese, Urdu.

---

## Legal Framework (India)

PROVCHAIN generates evidence and notices under:

- **Indian Copyright Act, 1957** — primary legal instrument
- **Information Technology Act, 2000** — platform takedown obligations
- **IT (Intermediary Guidelines) Rules, 2021** — 36-hour takedown mandate for Indian platforms
- **DMCA (Digital Millennium Copyright Act)** — for content on US-hosted platforms (YouTube, Meta)

> Indian platforms (ShareChat, Moj, Dailyhunt) are governed by IT Rules 2021.
> US platforms (YouTube, Instagram) respond to DMCA takedown notices.
> PROVCHAIN auto-selects the correct notice template based on platform jurisdiction.

**Timestamp legal standing:** OpenTimestamps anchors asset hashes into the Bitcoin
blockchain. RFC 3161 trusted timestamps are also generated. Both are admissible as
evidence of creation date in Indian civil proceedings under the Indian Evidence Act, 1872
(Section 65B — electronic records).

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PUBLISHER PORTAL                         │
│              (Cloud Run — React Frontend + FastAPI)              │
└────────────────────────────┬────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
┌─────────────────┐ ┌───────────────┐ ┌────────────────────┐
│  PILLAR 1       │ │  PILLAR 2     │ │  PILLAR 3          │
│  Asset          │ │  Propagation  │ │  Evidence          │
│  Registration   │ │  Monitor      │ │  Engine            │
└────────┬────────┘ └──────┬────────┘ └─────────┬──────────┘
         │                 │                     │
         ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      GOOGLE CLOUD LAYER                         │
│  Vertex AI Matching Engine │ Gemini Vision │ Gemini Text (12L)  │
│  Cloud Run │ Cloud Scheduler │ Firestore │ Firebase RTDB        │
│  Google Custom Search API │ Gmail API                           │
└─────────────────────────────────────────────────────────────────┘
         │                 │                     │
         ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DECENTRALIZED TRUST LAYER                    │
│         OpenTimestamps (Bitcoin) │ IPFS via Pinata              │
│         Wayback Machine API │ RFC 3161 Trusted Timestamp        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Three Pillars

### Pillar 1 — Pre-Publish Asset Registration

Every asset is fingerprinted before publishing using a dual-method system:

```
Asset (image / video keyframe / article text)
    │
    ├── pHash (perceptual hash)        → pixel-level duplicate detection
    ├── Gemini Vision Embedding        → semantic similarity (cropped, recolored)
    ├── SHA-256 hash                   → cryptographic identity
    │
    ├── RFC 3161 Trusted Timestamp     → legally recognized timestamp
    ├── OpenTimestamps → Bitcoin chain → tamper-proof blockchain anchor
    │
    └── Stored in:
            Firestore (asset registry + metadata)
            Vertex AI Matching Engine (embedding index)
            IPFS via Pinata (immutable registration certificate)
```

**Fingerprint Fusion Decision Architecture:**

```python
# Dual-threshold system — prevents false-positive DMCA notices
def match_decision(phash_similarity, embedding_cosine):
    if phash_similarity > 0.92:
        return "HIGH_CONFIDENCE"      # Auto-flag, queue for evidence generation
    elif embedding_cosine > 0.88:
        return "PROBABLE_MATCH"       # Queue for human review
    elif phash_similarity > 0.75 and embedding_cosine > 0.75:
        return "POSSIBLE_MATCH"       # Log only, no action
    else:
        return "NO_MATCH"

# DMCA notice generation requires: HIGH_CONFIDENCE + minimum 2 independent URLs
```

**Multilingual Metadata (Gemini Text — 12 Indian Languages):**
Article titles, captions, and alt-text are indexed in the source language. When a
scraped copy appears with translated or transliterated metadata, the semantic embedding
still catches it. Language detection is automatic.

---

### Pillar 2 — Propagation Velocity & Attribution Gap Analysis

**Core Insight:** Legitimate viral content travels differently from scraper farm distribution.
PROVCHAIN quantifies this difference using four measurable signals.

**Scan Schedule (Cloud Scheduler → Cloud Run):**

```
T+6h  → First scan  (early scraper farms activate within hours)
T+24h → Second scan (aggregator redistribution window)
T+72h → Third scan  (long-tail misappropriation)
T+7d  → Final scan
```

**Signals Computed Per Scan:**

```python
features = {
    # Signal 1: Velocity
    # Scraper farms: spike fast, plateau. Viral: gradual build.
    "velocity": new_instances / hours_since_last_scan,

    # Signal 2: Domain Entropy
    # Legitimate sharing: high diversity (many unique domains)
    # Scrapers: low diversity (5-10 farm domains repeat)
    "domain_entropy": shannon_entropy(unique_domains),

    # Signal 3: Attribution Gap
    # What % of instances credit the original source?
    "attribution_rate": credited_instances / total_instances,

    # Signal 4: Domain Risk Score (composite)
    "domain_risk": weighted_score(
        domain_age=whois_age(domain),       # Young domain = higher risk
        tranco_rank=get_rank(domain),       # Unranked = higher risk
        blacklist=mxtoolbox_check(domain),  # Blacklisted = immediate high risk
        tld_pattern=is_farm_tld(domain),    # .xyz, .click, .top = risk signal
    ),

    # Signal 5: Geographic Anomaly (via Google News API metadata)
    "geo_anomaly": unexpected_region_spike(metadata),
}

# Rule-based thresholding at MVP
# Upgrade path: Isolation Forest on accumulated scan data
def anomaly_decision(features):
    if features["domain_entropy"] < 1.2 and features["velocity"] > THRESHOLD:
        return "SCRAPER_FARM_SIGNATURE"
    if features["attribution_rate"] < 0.2 and features["total_instances"] > 50:
        return "MASS_MISAPPROPRIATION"
    if features["domain_risk"] > 0.8:
        return "HIGH_RISK_DISTRIBUTION"
```

**APIs Used for Scanning:**
- Google Custom Search API — text and image content indexed on Google
- Google Image Search API — reverse image search for visual assets
- Google News API — article distribution tracking
- Wayback Machine API — historical evidence recovery (when did the copy first appear?)

---

### Pillar 3 — Automated Evidence Package *(Demo Centerpiece)*

When an anomaly is confirmed, PROVCHAIN auto-generates a complete legal bundle:

```
evidence_bundle_{asset_id}_{timestamp}/
├── registration_certificate.pdf
│       SHA-256 hash, RFC 3161 timestamp proof, OpenTimestamps .ots file,
│       IPFS CID of original asset, Gemini embedding vector checksum
│
├── fingerprint_match_report.pdf
│       Side-by-side visual diff (original vs detected copy),
│       pHash similarity score, embedding cosine score, decision rationale
│
├── propagation_timeline.png
│       Velocity chart (instances over time), domain entropy graph,
│       geographic distribution map, attribution gap chart
│
├── infringing_urls.csv
│       All flagged URLs, domain risk scores, Wayback Machine archive links,
│       first-seen timestamps, platform jurisdiction (India/US)
│
├── legal_notice_{platform}.pdf
│       Auto-selected template:
│       → IT Rules 2021 notice (for ShareChat, Moj, Dailyhunt, JioCinema)
│       → DMCA takedown (for YouTube, Instagram, Twitter/X, Reddit)
│       Pre-filled: owner details, asset description, infringing URLs,
│       registration proof references
│
└── bundle_manifest.json
        IPFS CID of each file above (immutable, publicly verifiable)
        bundle_hash: SHA-256 of entire bundle
        ipfs_gateway: https://ipfs.io/ipfs/{CID}

IPFS makes this bundle permanent and independently verifiable by any court,
platform, or authority — PROVCHAIN is NOT the custodian of evidence.
```

**One-Click Send via Gmail API:**
Legal notice is pre-addressed to platform abuse/legal email.
Publisher reviews → clicks Send → Gmail API dispatches.
Sent timestamp logged to Firestore as part of enforcement record.

---

## Tech Stack

### Google Cloud (Core — Mandatory for Hackathon)

| Service | Role | Why |
|---|---|---|
| **Vertex AI Matching Engine** | ANN search on Gemini embeddings | Near real-time visual similarity at scale |
| **Gemini Vision API** | Image/video keyframe semantic embedding | Catches cropped, recolored, semantically similar copies |
| **Gemini Text (Vertex AI)** | Multilingual metadata analysis | 12 Indian languages, semantic understanding of captions/titles |
| **Google Custom Search API** | Scan Google-indexed content for asset copies | Legal, scalable, covers Indian aggregators |
| **Cloud Run** | Stateless scan jobs + API backend | Pay-per-request, scales to zero |
| **Cloud Scheduler** | Trigger T+6h, T+24h, T+72h, T+7d scans | Zero-maintenance periodic jobs |
| **Firebase Realtime DB** | Live anomaly alerts → publisher dashboard | Correct use: real-time push, not structured query |
| **Firestore** | Asset registry, scan history, job state | Structured queries, scales, not RTDB |
| **Gmail API** | Auto-generate and dispatch legal notices | One-click enforcement |

### Decentralized Trust Layer

| Service | Role | Cost |
|---|---|---|
| **OpenTimestamps** | Anchor SHA-256 hash into Bitcoin blockchain | Free |
| **RFC 3161** | Trusted timestamp (legally recognized, Indian Evidence Act) | Free (FreeTSA.org) |
| **IPFS via Pinata** | Immutable evidence bundle storage | Free tier: 1GB/month |
| **Wayback Machine API** | Historical copy detection + archive evidence | Free |

### Domain Intelligence Layer

| Service | Role | Cost |
|---|---|---|
| **WHOIS API** | Domain age scoring | Free tier |
| **Tranco List** | Domain popularity ranking (better than Alexa) | Free CSV |
| **MXToolbox API** | Spam/blacklist check | Free tier |

---

## Project Structure

```
provchain/
│
├── README.md
├── .env.example
├── docker-compose.yml
├── requirements.txt
│
├── core/
│   ├── __init__.py
│   ├── config.py                    # All env vars, thresholds, API keys
│   └── exceptions.py                # Custom exception hierarchy
│
├── registration/                    # PILLAR 1
│   ├── __init__.py
│   ├── fingerprint.py               # pHash + Gemini Vision embedding
│   ├── hasher.py                    # SHA-256, content normalization
│   ├── timestamp.py                 # RFC 3161 + OpenTimestamps
│   ├── ipfs_client.py               # Pinata SDK wrapper
│   ├── registry.py                  # Firestore asset registry CRUD
│   └── vertex_indexer.py            # Vertex AI Matching Engine upsert
│
├── monitoring/                      # PILLAR 2
│   ├── __init__.py
│   ├── scanner.py                   # Orchestrates all scan APIs
│   ├── google_search.py             # Custom Search + Image Search wrapper
│   ├── news_scanner.py              # Google News API wrapper
│   ├── wayback.py                   # Wayback Machine API client
│   ├── domain_scorer.py             # WHOIS + Tranco + MXToolbox scoring
│   ├── propagation_analyzer.py      # Velocity, entropy, attribution gap
│   └── anomaly_detector.py          # Rule-based threshold engine
│
├── evidence/                        # PILLAR 3
│   ├── __init__.py
│   ├── bundle_generator.py          # Orchestrates full evidence package
│   ├── pdf_builder.py               # ReportLab: registration cert + match report
│   ├── visual_diff.py               # Side-by-side image comparison (Pillow)
│   ├── chart_builder.py             # Propagation timeline charts (Matplotlib)
│   ├── notice_generator.py          # Legal notice template engine
│   ├── templates/
│   │   ├── dmca_notice.jinja2       # For YouTube, Instagram, Meta (US platforms)
│   │   ├── it_rules_notice.jinja2   # For ShareChat, Moj, Dailyhunt (Indian platforms)
│   │   └── copyright_act_notice.jinja2  # Direct infringement under Indian Copyright Act
│   └── gmail_sender.py              # Gmail API dispatch + logging
│
├── api/                             # FastAPI Backend
│   ├── __init__.py
│   ├── main.py                      # App entrypoint, CORS, middleware
│   ├── routes/
│   │   ├── register.py              # POST /register — asset registration
│   │   ├── scan.py                  # POST /scan/{asset_id} — manual trigger
│   │   ├── alerts.py                # GET /alerts — publisher alert feed
│   │   ├── evidence.py              # GET /evidence/{asset_id} — bundle download
│   │   └── notice.py               # POST /notice/send — Gmail dispatch
│   └── middleware/
│       ├── auth.py                  # Firebase Auth token validation
│       └── rate_limiter.py          # Per-publisher scan rate limiting
│
├── jobs/                            # Cloud Run Jobs (triggered by Cloud Scheduler)
│   ├── scheduled_scan.py            # Main scan orchestrator
│   ├── evidence_generator.py        # Evidence bundle on anomaly confirm
│   └── cleanup.py                   # Purge expired scan results
│
├── frontend/                        # React (deployed on Cloud Run)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx        # Live anomaly feed (Firebase RTDB)
│   │   │   ├── Register.jsx         # Asset upload + registration flow
│   │   │   ├── AssetDetail.jsx      # Per-asset scan history + evidence
│   │   │   └── EvidenceViewer.jsx   # Bundle preview + one-click send
│   │   └── components/
│   │       ├── PropagationChart.jsx # Velocity + entropy visualizations
│   │       ├── DomainRiskBadge.jsx  # Risk score display
│   │       └── IPFSVerifier.jsx     # IPFS CID verification widget
│   └── public/
│
├── scripts/
│   ├── seed_registry.py             # Dev: populate Firestore with test assets
│   ├── test_scan.py                 # Dev: run scan on a known infringing URL
│   └── verify_bundle.py             # Verify IPFS CID + OTS proof integrity
│
└── tests/
    ├── test_fingerprint.py
    ├── test_propagation_analyzer.py
    ├── test_anomaly_detector.py
    ├── test_evidence_generator.py
    └── test_notice_generator.py
```

---

## Module Breakdown

### `registration/fingerprint.py`

```python
import imagehash
from PIL import Image
import vertexai
from vertexai.vision_models import MultiModalEmbeddingModel

def compute_phash(image_path: str) -> str:
    img = Image.open(image_path)
    return str(imagehash.phash(img))

def compute_gemini_embedding(image_path: str) -> list[float]:
    model = MultiModalEmbeddingModel.from_pretrained("multimodalembedding@001")
    image = vertexai.vision_models.Image.load_from_file(image_path)
    embeddings = model.get_embeddings(image=image)
    return embeddings.image_embedding  # 1408-dim vector

def compute_text_embedding(text: str, language: str) -> list[float]:
    # Gemini Text handles all 12 Indian languages natively
    from vertexai.language_models import TextEmbeddingModel
    model = TextEmbeddingModel.from_pretrained("text-multilingual-embedding-002")
    return model.get_embeddings([text])[0].values
```

### `registration/timestamp.py`

```python
import hashlib, requests
from opentimestamps.core.timestamp import DetachedTimestampFile
import opentimestamps.calendar

def rfc3161_timestamp(file_hash: str) -> bytes:
    """FreeTSA.org — free, legally recognized RFC 3161 timestamp"""
    tsr = requests.post(
        "https://freetsa.org/tsr",
        data=_build_tsr_request(file_hash),
        headers={"Content-Type": "application/timestamp-query"}
    )
    return tsr.content  # .tsr file — include in evidence bundle

def opentimestamps_stamp(file_hash: bytes) -> str:
    """Anchor hash into Bitcoin blockchain via OpenTimestamps"""
    import opentimestamps.calendar
    stamp = DetachedTimestampFile(file_hash)
    calendar = opentimestamps.calendar.RemoteCalendar("https://alice.btc.calendar.opentimestamps.org")
    calendar.submit(stamp.timestamp)
    return stamp  # .ots proof file — confirmed after ~1 Bitcoin block (~10 min)
```

### `monitoring/propagation_analyzer.py`

```python
import math
from collections import Counter
from dataclasses import dataclass

@dataclass
class PropagationFeatures:
    velocity: float               # instances per hour
    domain_entropy: float         # Shannon entropy of domain list
    attribution_rate: float       # fraction citing original source
    domain_risk_avg: float        # mean risk score across all domains
    geo_anomaly_score: float      # unexpected regional spike

def compute_features(scan_results: list[dict], hours_elapsed: float) -> PropagationFeatures:
    domains = [r["domain"] for r in scan_results]
    domain_counts = Counter(domains)
    total = len(scan_results)

    # Shannon entropy — low entropy = few domains dominating = scraper signal
    entropy = -sum((c/total) * math.log2(c/total) for c in domain_counts.values())

    credited = sum(1 for r in scan_results if r.get("cites_original", False))

    return PropagationFeatures(
        velocity=total / max(hours_elapsed, 1),
        domain_entropy=entropy,
        attribution_rate=credited / max(total, 1),
        domain_risk_avg=sum(r["domain_risk"] for r in scan_results) / max(total, 1),
        geo_anomaly_score=_compute_geo_anomaly(scan_results),
    )

def classify_anomaly(features: PropagationFeatures) -> str:
    if features.domain_entropy < 1.2 and features.velocity > 20:
        return "SCRAPER_FARM_SIGNATURE"
    if features.attribution_rate < 0.15 and features.velocity > 5:
        return "MASS_MISAPPROPRIATION"
    if features.domain_risk_avg > 0.75:
        return "HIGH_RISK_DISTRIBUTION"
    return "NORMAL"
```

### `evidence/notice_generator.py`

```python
from jinja2 import Environment, FileSystemLoader
import pycountry

PLATFORM_JURISDICTION = {
    "youtube.com":      "DMCA",
    "instagram.com":    "DMCA",
    "facebook.com":     "DMCA",
    "twitter.com":      "DMCA",
    "reddit.com":       "DMCA",
    "sharechat.com":    "IT_RULES_2021",
    "moj.in":           "IT_RULES_2021",
    "dailyhunt.in":     "IT_RULES_2021",
    "jiosaavn.com":     "IT_RULES_2021",
    "jiocinema.com":    "IT_RULES_2021",
    "default":          "COPYRIGHT_ACT_1957",
}

def generate_notice(asset: dict, infringing_urls: list, owner: dict) -> dict:
    jurisdiction = _detect_jurisdiction(infringing_urls)
    template_map = {
        "DMCA":             "dmca_notice.jinja2",
        "IT_RULES_2021":    "it_rules_notice.jinja2",
        "COPYRIGHT_ACT_1957": "copyright_act_notice.jinja2",
    }
    env = Environment(loader=FileSystemLoader("evidence/templates"))
    template = env.get_template(template_map[jurisdiction])
    return {
        "jurisdiction": jurisdiction,
        "notice_html": template.render(asset=asset, urls=infringing_urls, owner=owner),
        "platform_abuse_email": _get_abuse_email(infringing_urls[0]["domain"]),
    }
```

---

## Data Flow

```
Publisher uploads asset
        │
        ▼
[fingerprint.py]
    pHash + Gemini Vision Embedding + SHA-256
        │
        ├──► [vertex_indexer.py] → Vertex AI Matching Engine
        ├──► [timestamp.py]      → RFC 3161 + OpenTimestamps (.ots)
        ├──► [ipfs_client.py]    → IPFS registration certificate
        └──► [registry.py]       → Firestore asset record
        │
        ▼
Cloud Scheduler fires at T+6h, T+24h, T+72h, T+7d
        │
        ▼
[scanner.py]
    Google Custom Search + Image Search + News API + Wayback Machine
        │
        ▼
[domain_scorer.py]
    WHOIS + Tranco + MXToolbox per discovered domain
        │
        ▼
[propagation_analyzer.py]
    Velocity + Entropy + Attribution Rate + Domain Risk + Geo Anomaly
        │
        ▼
[anomaly_detector.py]
    Classify: NORMAL / SCRAPER_FARM / MASS_MISAPPROPRIATION / HIGH_RISK
        │
        ├── NORMAL → log to Firestore, no action
        │
        └── ANOMALY CONFIRMED
                │
                ├──► Firebase RTDB → live dashboard alert (publisher sees instantly)
                │
                └──► [bundle_generator.py]
                        registration_certificate.pdf
                        fingerprint_match_report.pdf
                        propagation_timeline.png
                        infringing_urls.csv
                        legal_notice_{jurisdiction}.pdf
                        bundle_manifest.json
                              │
                              ├──► IPFS via Pinata (immutable storage)
                              └──► Firestore (bundle reference + IPFS CID)
                                        │
                                        ▼
                              Publisher clicks "Send Notice"
                                        │
                              [gmail_sender.py] → Gmail API dispatch
                                        │
                              Sent timestamp logged to Firestore
```

---

## Evidence Bundle Spec

Every evidence bundle is content-addressed on IPFS. The IPFS CID is included in the
legal notice. Any court, platform, or authority can independently verify the bundle
at `https://ipfs.io/ipfs/{CID}` — PROVCHAIN is not the custodian.

```json
{
  "bundle_version": "1.0",
  "asset_id": "asset_abc123",
  "generated_at": "2025-04-24T10:30:00Z",
  "registration": {
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "phash": "a4c2f8e3b1d09e4f",
    "rfc3161_timestamp": "2025-04-20T08:00:00Z",
    "ots_proof_ipfs_cid": "QmXoyp...proof",
    "registration_cert_ipfs_cid": "QmAbcd...cert"
  },
  "detection": {
    "scan_timestamp": "2025-04-24T10:00:00Z",
    "total_instances_found": 47,
    "anomaly_type": "MASS_MISAPPROPRIATION",
    "propagation_features": {
      "velocity": 12.3,
      "domain_entropy": 0.89,
      "attribution_rate": 0.08,
      "domain_risk_avg": 0.81
    }
  },
  "evidence_files": {
    "registration_certificate": "ipfs://QmReg...",
    "fingerprint_report":       "ipfs://QmFin...",
    "propagation_timeline":     "ipfs://QmPro...",
    "infringing_urls_csv":      "ipfs://QmUrl...",
    "legal_notice":             "ipfs://QmNot..."
  },
  "notice": {
    "jurisdiction": "IT_RULES_2021",
    "platform": "sharechat.com",
    "abuse_email": "abuse@sharechat.com",
    "sent_at": null,
    "gmail_message_id": null
  },
  "bundle_ipfs_cid": "QmBundle...",
  "bundle_sha256": "f7c3bc..."
}
```

---

## Deployment

### Prerequisites

```bash
# Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  firestore.googleapis.com \
  firebase.googleapis.com \
  gmail.googleapis.com \
  customsearch.googleapis.com

# Python deps
pip install -r requirements.txt

# Environment
cp .env.example .env
# Fill: GOOGLE_CLOUD_PROJECT, VERTEX_INDEX_ID, GEMINI_API_KEY,
#        PINATA_JWT, FIREBASE_CONFIG, CUSTOM_SEARCH_CX
```

### Deploy API + Frontend

```bash
# Build and deploy backend
gcloud run deploy provchain-api \
  --source ./api \
  --region asia-south1 \       # Mumbai — lowest latency for Indian users
  --allow-unauthenticated

# Deploy scan jobs
gcloud run jobs deploy provchain-scanner \
  --source ./jobs \
  --region asia-south1

# Schedule scan triggers (Cloud Scheduler)
gcloud scheduler jobs create http provchain-scan-t6h \
  --schedule="0 */6 * * *" \
  --uri="https://provchain-scanner-...run.app/scan" \
  --location=asia-south1
```

### Firebase RTDB Rules

```json
{
  "rules": {
    "alerts": {
      "$publisherId": {
        ".read": "$publisherId === auth.uid",
        ".write": false
      }
    }
  }
}
```

---

## Cost Model

| Service | Free Tier | Estimated Cost (100 assets/day) |
|---|---|---|
| Google Custom Search API | 100 queries/day | ~$15–20/month |
| Vertex AI Matching Engine | — | ~$65/month (min) |
| Gemini Vision API | 1,500 req/day | Free at hackathon scale |
| Cloud Run | 2M req/month | ~$5–10/month |
| Cloud Scheduler | 3 jobs free | Free |
| Firestore | 1GB free | Free at hackathon scale |
| OpenTimestamps | Unlimited | Free |
| IPFS via Pinata | 1GB/month | Free |
| Wayback Machine | Unlimited | Free |
| WHOIS / Tranco / MXToolbox | Free tier | Free |
| **Total** | | **~$85–100/month** |

> Production path: Replace Vertex AI Matching Engine with Qdrant on Cloud Run (~$10–15/month)
> to bring total cost under $30/month for small Indian publishers.

---

## Roadmap

| Phase | Milestone | Timeline |
|---|---|---|
| **MVP (Hackathon)** | Registration + Basic Scan + Evidence Bundle Demo | Week 1 |
| **v1.0** | Full propagation analysis + IT Rules 2021 notices | Month 1 |
| **v1.1** | ShareChat / Moj API integration (direct monitoring) | Month 2 |
| **v2.0** | Isolation Forest on accumulated scan data (ML anomaly detection) | Month 4 |
| **v2.1** | WhatsApp forwarding chain detection (major Indian misappropriation vector) | Month 5 |
| **v3.0** | Publisher cooperative — shared scraper domain blocklist | Month 8 |

---

## License

This project is submitted to [Hackathon Name] under the competition's IP terms.
All code © 2025 Team PROVCHAIN. Contact: [your email]

---

*Built for Indian publishers. Powered by Google Cloud. Anchored on Bitcoin.*
