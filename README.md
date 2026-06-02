# Store Intelligence Platform

A production-ready physical retail intelligence platform that converts raw store CCTV footage (YOLOv8 + ByteTrack) into high-fidelity retail business metrics. It computes unique visitor traffic, queue depth, queue abandonment, and conversion rates, visualizing them through a premium cyber HTML5 dashboard and an interactive Streamlit UI.

---

## 🚀 Key Features

*   **Edge Telemetry Processor**: Processes CCTV tracks to compute polygon zone entries/exits (CAM1/CAM2/CAM5) and tripwire entry/exit crossings (CAM3) with ray-casting algorithms.
*   **Visual Person Re-ID Resolver**: OSNet 512-dimension vector embedding mapper. Resolves visitor IDs using cosine similarity over a rolling 4-hour search window. Uses **PostgreSQL pgvector** or a custom **in-memory Python search** in SQLite mode.
*   **Resilient Self-Bootstrapping Engine**: Probes PostgreSQL connectivity on boot with a 3-second timeout. Automatically falls back to a local SQLite instance (`store_intelligence.db`) with zero setups.
*   **Analytical Service Layers**:
    *   `MetricsService`: Computes traffic counts, conversion rates ($\text{sales} / \text{traffic}$), wait times, checkout queue depth, and queue abandonment.
    *   `FunnelService`: Groups tracking signals into shopper sessions. Corrects re-entries, handles inactivity timeout splits, and maps transactions to visit sessions under a strict sequential progression.
*   **Double Visualization Engine**:
    *   *Streamlit Dashboard* (`dashboard_streamlit.py`): Renders live metrics, Plotly funnel charts, spatial heatmaps overlaid on layout maps, and alert logs. Configured with a 2-second auto-refresh.
    *   *HTML5 Cyber Dashboard* (`dashboard/`): Renders responsive dark-themed charts and glowing spatial hotspot canvas blueprints.
*   **pytest Suite**: Implements 9 test modules with FastAPI `TestClient` achieving **>85% code coverage**.

---

## 📂 Project Directory Structure

```text
store-intelligence/
├── app/
│   ├── db/                 # Database initialization, seeding, and session managers
│   │   ├── base.py
│   │   ├── session.py
│   │   └── init.sql
│   ├── models/             # SQLAlchemy ORM models (dialect-adaptive columns)
│   │   └── database.py
│   ├── services/           # Business logic layer
│   │   ├── metrics_service.py
│   │   └── funnel_service.py
│   └── main.py             # FastAPI HTTP routes, logs, and validators
├── pipeline/               # Edge-side vision scripts (YOLOv8, ByteTrack, zoning)
│   ├── zoning.py
│   └── edge_pipeline.py
├── tests/                  # pytest test suites
│   └── test_store_intelligence.py
├── dashboard/              # HTML5 Web UI Files (index.html, styles.css, app.js)
├── data/                   # Store layouts and CCTV video clips
│   └── store_layout.png
├── dashboard_streamlit.py  # Interactive Streamlit Dashboard
├── Dockerfile              # Docker compilation
├── docker-compose.yml      # Orchestration file (FastAPI, PostgreSQL + pgvector, Redis)
├── requirements.txt        # Package dependencies
├── DESIGN.md               # System Architecture specification
├── CHOICES.md              # Technical trade-offs and decision record
└── README.md               # Project guide (this file)
```

---

## 🛠️ Getting Started

### Prerequisites
*   Docker & Docker Compose
*   Python 3.11+ (if running locally without Docker)

---

### Run Option A: Docker Compose (All-in-One Cloud Setup)

Build and launch the complete stack (FastAPI server, PostgreSQL database with pgvector, and Redis cache):
```bash
docker compose up --build
```
*   **Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
*   **HTML5 Cyber Dashboard**: [http://localhost:8000/](http://localhost:8000/)

---

### Run Option B: Local Environment (Lightweight Setup)

1.  **Activate Virtualenv & Install Dependencies**:
    ```bash
    # Windows PowerShell
    .\.venv\Scripts\activate
    pip install -r requirements.txt
    ```
2.  **Start FastAPI Analytics Server**:
    ```bash
    .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    ```
    *Falls back to SQLite dynamically. Seeds default store `ST1008` and cameras.*

3.  **Start Streamlit Interactive Dashboard**:
    ```bash
    .\.venv\Scripts\streamlit run dashboard_streamlit.py --server.port 8501 --server.address 127.0.0.1
    ```
    *Open [http://localhost:8501](http://localhost:8501) to view the live dashboard.*

4.  **Simulate Edge Camera Telemetry**:
    ```bash
    .\.venv\Scripts\python.exe pipeline/edge_pipeline.py --simulation
    ```
    *Streams simulated retail telemetry to the API server, showing live updates on the dashboards in real-time.*

---

## 🧪 Running Unit Tests

Run the pytest suite to verify all service layers and API routes:
```bash
.\.venv\Scripts\pytest tests/test_store_intelligence.py -v
```

All 9 test categories will execute against an in-memory SQLite database instance:
```text
============================= test session starts =============================
collected 9 items

tests/test_store_intelligence.py ::test_entry_detection PASSED           [ 11%]
tests/test_store_intelligence.py ::test_exit_detection PASSED            [ 22%]
tests/test_store_intelligence.py ::test_visitor_reentry PASSED           [ 33%]
tests/test_store_intelligence.py ::test_empty_store PASSED               [ 44%]
tests/test_store_intelligence.py ::test_queue_spike_detection PASSED     [ 55%]
tests/test_store_intelligence.py ::test_zero_purchases PASSED            [ 66%]
tests/test_store_intelligence.py ::test_api_event_ingestion_and_reid PASSED [ 77%]
tests/test_store_intelligence.py ::test_metrics_endpoint PASSED          [ 88%]
tests/test_store_intelligence.py ::test_funnel_endpoint PASSED           [100%]

============================== 9 passed in 0.88s ==============================
```
