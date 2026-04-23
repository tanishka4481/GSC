# PROVCHAIN

> **Content ID for everyone — not just the top 0.1%.**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18%2B-61DAFB)](https://react.dev/)
[![GCP](https://img.shields.io/badge/Google%20Cloud-Powered-4285F4)](https://cloud.google.com/)
[![Status](https://img.shields.io/badge/status-hackathon%20build-orange)]()

Unified digital asset intelligence platform for Indian publishers — register content, detect propagation anomalies, and generate legally-ready evidence bundles in minutes.

---

## The Problem

Regional news agencies, educational institutions, and independent publishers in India lose attribution, revenue, and legal control over their digital assets the moment they publish. Content is scraped and reposted across ShareChat, Moj, Dailyhunt, YouTube, and regional aggregators — without credit, payment, or permission.

Enterprise-grade content protection (Nielsen, Audible Magic, YouTube Content ID) is inaccessible to Indian publishers by cost and infrastructure. **PROVCHAIN bridges that gap.**

---

## What PROVCHAIN Does

| Pillar | What it does |
|--------|--------------|
| **1. Asset Registration** | Fingerprint content before publishing — pHash + Gemini Vision embedding + SHA-256, anchored on Bitcoin via OpenTimestamps |
| **2. Propagation Monitor** | Detect scraping vs legitimate sharing using velocity, domain entropy, attribution gap, and domain risk signals |
| **3. Evidence Engine** | Auto-generate a complete legal bundle — registration certificate, match report, propagation charts, and a pre-filled DMCA or IT Rules 2021 notice |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│               PUBLISHER PORTAL                  │
│         React Frontend  +  FastAPI Backend       │
└────────────────┬────────────────────────────────┘
                 │
      ┌──────────┼──────────┐
      ▼          ▼          ▼
  Pillar 1   Pillar 2   Pillar 3
  Register   Monitor    Evidence
      │          │          │
      └──────────┼──────────┘
                 ▼
     ┌───────────────────────┐
     │    Google Cloud       │
     │  Vertex AI · Gemini   │
     │  Firestore · Firebase │
     │  Cloud Run · Gmail    │
     └───────────┬───────────┘
                 ▼
     ┌───────────────────────┐
     │  Decentralized Trust  │
     │  OpenTimestamps (BTC) │
     │  IPFS via Pinata      │
     │  RFC 3161 Timestamp   │
     └───────────────────────┘
```

---

## Legal Coverage

PROVCHAIN generates evidence and notices under:

- **Indian Copyright Act, 1957** — primary instrument
- **IT Act, 2000** + **IT Rules 2021** — 36-hour takedown mandate for Indian platforms (ShareChat, Moj, Dailyhunt)
- **DMCA** — for US-hosted platforms (YouTube, Instagram, Meta)

Timestamps are admissible under **Indian Evidence Act, 1872 (Section 65B)**.

---

## Tech Stack

### Backend
- **FastAPI** — REST API
- **Vertex AI Matching Engine** — ANN search on Gemini embeddings
- **Gemini Vision API** — semantic image/video fingerprinting
- **Gemini Text (multilingual)** — 12 Indian languages
- **Google Custom Search API** — content propagation scanning
- **Cloud Run** — stateless scan jobs
- **Cloud Scheduler** — T+6h, T+24h, T+72h, T+7d scan triggers
- **Firestore** — asset registry and scan history
- **Firebase RTDB** — real-time publisher alerts

### Frontend
- **React 18** — publisher portal
- **Recharts** — propagation visualizations
- **Firebase JS SDK** — real-time dashboard

### Trust Layer
- **OpenTimestamps** — Bitcoin blockchain anchoring (free)
- **RFC 3161 / FreeTSA.org** — legally recognized timestamps (free)
- **IPFS via Pinata** — immutable evidence bundle storage (free tier)
- **Wayback Machine API** — historical copy evidence (free)

### Domain Intelligence
- **WHOIS API** — domain age scoring
- **Tranco List** — domain popularity ranking
- **MXToolbox** — spam/blacklist check

---

## Project Structure

```
provchain/
├── core/
│   ├── config.py             # All env vars and thresholds
│   └── exceptions.py         # Custom exception hierarchy
│
├── registration/             # Pillar 1
│   ├── fingerprint.py        # pHash + Gemini Vision embedding
│   ├── hasher.py             # SHA-256
│   ├── timestamp.py          # RFC 3161 + OpenTimestamps
│   ├── ipfs_client.py        # Pinata wrapper
│   ├── registry.py           # Firestore CRUD
│   └── vertex_indexer.py     # Vertex AI Matching Engine
│
├── monitoring/               # Pillar 2
│   ├── scanner.py            # Scan orchestrator
│   ├── google_search.py      # Custom Search + Image Search
│   ├── news_scanner.py       # Google News API
│   ├── wayback.py            # Wayback Machine client
│   ├── domain_scorer.py      # WHOIS + Tranco + MXToolbox
│   ├── propagation_analyzer.py  # 5-signal feature engine
│   └── anomaly_detector.py   # Rule-based classification
│
├── evidence/                 # Pillar 3
│   ├── bundle_generator.py   # Full evidence package
│   ├── pdf_builder.py        # ReportLab PDFs
│   ├── visual_diff.py        # Side-by-side image comparison
│   ├── chart_builder.py      # Matplotlib propagation charts
│   ├── notice_generator.py   # Legal notice template engine
│   ├── gmail_sender.py       # Gmail API dispatch
│   └── templates/
│       ├── dmca_notice.jinja2
│       ├── it_rules_notice.jinja2
│       └── copyright_act_notice.jinja2
│
├── api/
│   ├── main.py
│   ├── routes/
│   │   ├── register.py       # POST /register
│   │   ├── scan.py           # POST /scan/{asset_id}
│   │   ├── alerts.py         # GET /alerts
│   │   ├── evidence.py       # GET /evidence/{asset_id}
│   │   └── notice.py         # POST /notice/send
│   └── middleware/
│       ├── auth.py
│       └── rate_limiter.py
│
├── jobs/
│   ├── scheduled_scan.py
│   ├── evidence_generator.py
│   └── cleanup.py
│
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Dashboard.jsx
│       │   ├── Register.jsx
│       │   ├── AssetDetail.jsx
│       │   └── EvidenceViewer.jsx
│       └── components/
│           ├── PropagationChart.jsx
│           ├── DomainRiskBadge.jsx
│           └── IPFSVerifier.jsx
│
├── scripts/
│   ├── seed_registry.py
│   ├── test_scan.py
│   └── verify_bundle.py
│
├── tests/
│   ├── test_fingerprint.py
│   ├── test_propagation_analyzer.py
│   ├── test_anomaly_detector.py
│   ├── test_evidence_generator.py
│   └── test_notice_generator.py
│
├── .env.example
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Google Cloud account
- Pinata account (IPFS)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/provchain.git
cd provchain
pip install -r requirements.txt
```

### 2. Set up environment

```bash
cp .env.example .env
```

Fill in your `.env`:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
VERTEX_INDEX_ID=your-index-id
GEMINI_API_KEY=your-key
PINATA_JWT=your-pinata-jwt
FIREBASE_CONFIG={"apiKey": "...", ...}
CUSTOM_SEARCH_CX=your-cx-id
```

### 3. Enable GCP services

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  firestore.googleapis.com \
  firebase.googleapis.com \
  gmail.googleapis.com \
  customsearch.googleapis.com
```

### 4. Run locally

```bash
uvicorn api.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

---

## Deploy to Google Cloud

```bash
# Backend
gcloud run deploy provchain-api \
  --source ./api \
  --region asia-south1 \
  --allow-unauthenticated

# Scan jobs
gcloud run jobs deploy provchain-scanner \
  --source ./jobs \
  --region asia-south1

# Cloud Scheduler
gcloud scheduler jobs create http provchain-scan-t6h \
  --schedule="0 */6 * * *" \
  --uri="https://provchain-scanner-....run.app/scan" \
  --location=asia-south1
```

---

## Fingerprint Decision Logic

```python
def match_decision(phash_similarity, embedding_cosine):
    if phash_similarity > 0.92:
        return "HIGH_CONFIDENCE"    # Auto-flag
    elif embedding_cosine > 0.88:
        return "PROBABLE_MATCH"     # Human review
    elif phash_similarity > 0.75 and embedding_cosine > 0.75:
        return "POSSIBLE_MATCH"     # Log only
    else:
        return "NO_MATCH"

# DMCA notice requires: HIGH_CONFIDENCE + minimum 2 independent URLs
```

---

## Evidence Bundle Structure

Every bundle is content-addressed on IPFS. Independently verifiable by any court or platform.

```
evidence_bundle_{asset_id}_{timestamp}/
├── registration_certificate.pdf
├── fingerprint_match_report.pdf
├── propagation_timeline.png
├── infringing_urls.csv
├── legal_notice_{jurisdiction}.pdf
└── bundle_manifest.json
```

IPFS CID is embedded in every legal notice — no one needs to trust PROVCHAIN as a custodian.

---

## Cost Estimate (100 assets/day)

| Service | Cost |
|---------|------|
| Google Custom Search API | ~$15–20/month |
| Vertex AI Matching Engine | ~$65/month |
| Gemini Vision API | Free at hackathon scale |
| Cloud Run + Scheduler | ~$5–10/month |
| Firestore, IPFS, OpenTimestamps | Free |
| **Total** | **~$85–100/month** |

> Production path: replace Vertex AI Matching Engine with Qdrant on Cloud Run (~$10–15/month) to bring total under $30/month.

---

## Roadmap

| Phase | Milestone |
|-------|-----------|
| MVP (Hackathon) | Registration + scan + evidence bundle demo |
| v1.0 | Full propagation analysis + IT Rules 2021 notices |
| v1.1 | ShareChat / Moj API direct monitoring |
| v2.0 | Isolation Forest ML anomaly detection |
| v2.1 | WhatsApp forwarding chain detection |
| v3.0 | Publisher cooperative — shared scraper blocklist |

---

## Target Users

| Segment | Pain point |
|---------|------------|
| Regional news agencies | Articles scraped by Dailyhunt without credit |
| Educational content boards | NCERT/CBSE material redistributed illegally |
| Independent media houses | Visual content misappropriated at scale |

**Language coverage:** Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese, Urdu.

---

## Contributing

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Make changes, then commit
git add .
git commit -m "feat: short description of what you did"

# Push and open a PR
git push origin feature/your-feature-name
```

**Commit message format:**
- `feat:` new feature
- `fix:` bug fix
- `docs:` README or comment updates
- `refactor:` code restructure, no behavior change
- `test:` adding or fixing tests

---

## License

© 2025 Team PROVCHAIN. All rights reserved.

*Built for Indian publishers. Powered by Google Cloud. Anchored on Bitcoin.*