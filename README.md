# 🇮🇳 MPLAD FraudShield

**AI-Powered Forensic Audit, Fiscal Integrity & Anti-Corruption Analytics for MPLADS**  
*Built for Smart India Hackathon (SIH 2025)*

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)

---

## 🎯 Problem Statement

The **Members of Parliament Local Area Development Scheme (MPLADS)** allocates ₹5 Crore annually per Member of Parliament for developmental public works. However, monitoring over 100,000+ distributed projects across 543 constituencies faces immense challenges: manual audit backlogs, fraudulent contractor cartels, ghost infrastructure that exists only on paper, synthetic work splitting to evade statutory tender thresholds, fund recycling across financial year boundaries, and lack of direct civic feedback loops. **MPLAD FraudShield** solves this by ingesting multi-modal fiscal, geographic, and citizen sentiment data to deliver automated forensic audits and early fraud detection before public funds are siphoned.

---

## 🛡️ 3-Layer Forensic Solution Overview

```
                      ┌───────────────────────────────────────────────┐
                      │    MPLADS Data / CSV / GeoJSON / Feedback     │
                      └──────────────────────┬────────────────────────┘
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      ▼                                      ▼                                      ▼
┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────────┐
│ Layer 1: Rule Engine      │  │ Layer 2: Machine Learning │  │ Layer 3: NLP & Geo Engine │
├───────────────────────────┤  ├───────────────────────────┤  ├───────────────────────────┤
│ • Tender splitting (₹49L) │  │ • Isolation Forest        │  │ • Duplicate semantic text │
│ • Round number anomalies  │  │ • Cost/Duration Outliers  │  │ • Sentiment divergence    │
│ • Vendor concentration    │  │ • Multi-ratio Anomaly     │  │ • OSM Ghost asset lookup  │
│ • Phantom fast completions│  │ • Fiscal Drift Profiler   │  │ • Duplicate GPS detection │
└─────────────┬─────────────┘  └─────────────┬─────────────┘  └─────────────┬─────────────┘
              │                              │                              │
              └──────────────────────────────┼──────────────────────────────┘
                                             ▼
                             ┌───────────────────────────────┐
                             │  Composite Risk Aggregator    │
                             │  (LOW | MEDIUM | HIGH | CRIT) │
                             └───────────────┬───────────────┘
                                             ▼
                             ┌───────────────────────────────┐
                             │ Executive Forensic Dashboard  │
                             └───────────────────────────────┘
```

1. **Layer 1 — Deterministic Red Flag Engine**: Enforces government procurement rules, detecting tender splitting just under the ₹50 Lakh statutory threshold (e.g., ₹49.5L), repetitive single-vendor allocations, round-number disbursements, rapid synthetic completions (e.g., ₹2 Cr hospital built in 3 days), and year-end budget exhaustion rushes.
2. **Layer 2 — Unsupervised Machine Learning Engine**: Employs **Isolation Forest** models and multidimensional fiscal ratio estimators to isolate statistical anomalies in cost-per-unit, expenditure velocity, duration anomalies, and multi-parameter fiscal irregularities across state and work categories.
3. **Layer 3 — NLP & Geospatial Forensic Scanner**: Uses **Sentence-Transformers** to cross-match work descriptions for plagiarism and synthetic duplicate projects, analyzes citizen survey grievance sentiment, and leverages **OpenStreetMap (Overpass API)** and geospatial clustering to detect duplicate coordinates and ghost projects.

---

## ✨ Key Features

- 📊 **Executive Overview Dashboard**: High-level fiscal tracking, risk distribution metrics, and interactive constituency heatmaps.
- 🚨 **Red Flag Anomaly Explorer**: Filter and inspect projects by risk severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) and triggered rule codes.
- 🕸️ **Vendor Collusion & Cartel Graph**: Interactive D3 force-directed visualizer mapping contractor networks, shell company clusters, and tender monopolization.
- 🗺️ **Geospatial & Ghost Project Detector**: Interactive Leaflet maps pinpointing duplicate GPS coordinates and physically impossible project sites.
- 👥 **Citizen Sentinel Feedback Survey**: Crowdsourced mobile ground-truth verification module allowing local citizens to submit ratings, comments, and photographic evidence, feeding directly into NLP sentiment scoring.
- 📄 **Executive Forensic Audit Reports**: One-click printable forensic dossiers with Gemini AI-generated executive summaries and evidence breakdowns.
- 📥 **Automated Data Ingestion & Scoring**: Real-time batch CSV ingestion that automatically executes the multi-engine audit pipeline.

---

## 💻 Tech Stack

| Domain | Technology / Library | Purpose |
| :--- | :--- | :--- |
| **Backend API** | FastAPI, Uvicorn, Python 3.11 | High-performance asynchronous REST API |
| **Frontend UI** | React 18, Vite 5, Tailwind CSS, Lucide Icons | Responsive modern forensic dashboard |
| **Database & ORM** | PostgreSQL 15, SQLite (Dev), SQLAlchemy 2.0 | Transactional storage and analytical schemas |
| **Caching & Tasks** | Redis 7, Celery | Asynchronous scoring pipeline and caching |
| **Machine Learning** | Scikit-learn (Isolation Forest), Pandas, NumPy | Anomaly detection and fiscal ratio statistics |
| **NLP & AI** | Sentence-Transformers, Google Gemini API | Text similarity, sentiment analysis, AI summaries |
| **Geospatial** | Overpy (OpenStreetMap Overpass API), Leaflet | GIS coordinates and infrastructure cross-verification |
| **Visualizations** | Recharts, D3.js Force Graphs | Financial trend charts and vendor cartel graphs |
| **DevOps & Deploy** | Docker, Docker Compose, Alpine Linux | Containerized multi-service orchestration |

---

## 🚀 Quick Start

### Option A: One-Click Demo (Recommended)

#### On Windows:
```cmd
scripts\start_demo.bat
```

#### On Linux / macOS:
```bash
chmod +x scripts/start_demo.sh
./scripts/start_demo.sh
```

---

### Option B: Docker Compose

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-org/mplad-fraudshield.git
   cd mplad-fraudshield
   ```

2. **Start all services**:
   ```bash
   docker-compose up -d
   ```

3. **Open the Dashboard**:
   - 🌐 **Frontend Dashboard**: [http://localhost:5173](http://localhost:5173)
   - 🔌 **Backend API**: [http://localhost:8000](http://localhost:8000)
   - 📖 **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### Option C: Manual Local Setup (Without Docker)

#### 1. Backend Setup:
```bash
cd backend
python -m venv .venv

# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
python startup_check.py
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Frontend Setup:
```bash
cd frontend
npm install
npm run dev
```

---

## 📂 Dataset Sources

| Dataset / Source | Description | Source Link |
| :--- | :--- | :--- |
| **Data.gov.in (Open Government Data)** | Official MPLADS sanctions, expenditure, and status records | [data.gov.in](https://data.gov.in) |
| **MoSPI MPLADS Portal** | Ministry of Statistics and Programme Implementation MPLADS portal | [mplads.gov.in](https://mplads.gov.in) |
| **OpenStreetMap (OSM Overpass)** | Public infrastructure layers for physical asset cross-checking | [openstreetmap.org](https://www.openstreetmap.org) |
| **Synthetic Forensic Dataset** | Injected fraud vectors (cartels, ghost projects, tender splitting) | `backend/data/sample_dataset.csv` |

---

## 📸 Screenshots

| Executive Overview Dashboard | Vendor Collusion Graph |
| :---: | :---: |
| *(Dashboard analytics, risk metrics, and red flags)* | *(D3 network graph of contractor clusters)* |

| Geospatial Ghost Project Map | Citizen Survey & Feedback Sentinel |
| :---: | :---: |
| *(Leaflet GPS verification & duplicate coordinates)* | *(Mobile-friendly citizen verification interface)* |

---

## 👥 Team Credits

Developed with ❤️ for **Smart India Hackathon (SIH 2025)**.

- **Domain**: Anti-Corruption, AI/ML & GovTech
- **Theme**: Smart Governance & Public Accountability
- **Organization**: Ministry of Statistics and Programme Implementation (MoSPI) / Government of India

---

## 📄 License
This project is licensed under the MIT License - see the `LICENSE` file for details.
