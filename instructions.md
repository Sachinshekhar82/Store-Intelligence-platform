# Instructions to Run the Store Intelligence Platform

This document outlines the step-by-step instructions to run, test, and verify the entire **Store Intelligence Platform** (FastAPI backend, Streamlit dashboard, YOLOv8 video extraction utility, and simulation edge pipeline).

---

## 🛠️ Option A: Local Python Environment (Recommended for local validation)

Follow these steps to set up the local environment, process CCTV videos, and launch the dashboards locally on Windows:

### 1. Setup Virtual Environment & Install Dependencies
Open **PowerShell** in the root of the project directory (`store-intelligence/`) and run:
```powershell
# Activate the virtual environment
.\.venv\Scripts\activate

# Install all standard requirements
pip install -r requirements.txt

# Install vision libraries for YOLOv8 video extraction
pip install opencv-python-headless ultralytics
```

### 2. Extract Heatmap Coordinates from MP4 Videos
Run the pre-processing script to parse coordinate telemetry directly from the camera feeds (`CAM1.mp4`, `CAM2.mp4`, `CAM3.mp4`, `CAM5.mp4` under the `data/` folder). This will populate your local SQLite database:
```powershell
python pipeline/extract_heatmap_coords.py
```
*This uses `yolov8n.pt` to detect shoppers and logs coordinates in `store_intelligence.db`. (It falls back to general object detections for placeholder clips that do not contain human figures).*

### 3. Start the FastAPI Analytics API Server
Launch the backend server locally (connects to the SQLite database by default):
```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
- **API Docs (Swagger UI)**: http://localhost:8000/docs
- **Web Canvas Heatmap UI**: http://localhost:8000/

### 4. Run the Streamlit Dashboard
Open a new terminal window, activate the virtual environment, and start the Streamlit UI:
```powershell
.\.venv\Scripts\activate
streamlit run dashboard_streamlit.py --server.port 8501 --server.address 127.0.0.1
```
- Open http://localhost:8501 in your browser.
- Select **Live API Backend** to view the coordinates populated from the video files.
- Select **Offline Simulator (Mock Data)** to demo dashboard charts offline.

### 5. Run the Edge Pipeline Simulator (Optional)
To stream additional real-time telemetry (visitor entries, zone dwells, checkout queue events) into the local dashboard, run:
```powershell
python pipeline/edge_pipeline.py --simulation
```

---

## 🐳 Option B: Running with Docker Compose (Production Environment)

To run the entire platform with a PostgreSQL database (+ pgvector extension for Re-ID) and Redis caching:

1. **Start the Stack**:
   ```bash
   docker compose up --build
   ```
2. **Access Services**:
   - **FastAPI Backend Server**: http://localhost:8000
   - **Interactive Web App**: http://localhost:8000/dashboard/
   - **API Docs**: http://localhost:8000/docs

---

## 🧪 Option C: Running Automated Tests

Run the pytest suite to verify all routing, funnel progression, Re-ID embedding matching, and queue alert services:
```powershell
python -m pytest tests/test_store_intelligence.py -v
```
