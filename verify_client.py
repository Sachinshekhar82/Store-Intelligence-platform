import datetime
import time
import httpx

BASE_URL = "http://localhost:8000"
STORE_ID = "ST1008"  # Seeded Store ID from init.sql

def test_api():
    print("=" * 60)
    print("STORE INTELLIGENCE API VERIFICATION CLIENT")
    print("=" * 60)

    # 1. Health check
    print("\n[1/5] Checking Service Health...")
    try:
        response = httpx.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Payload: {response.json()}")
    except Exception as e:
        print(f"Error reaching server: {e}")
        print("Please verify that your docker containers are running with 'docker compose up'.")
        return

    # 2. Event Ingestion
    print("\n[2/5] Simulating Visitor Event Ingestion...")
    payload = {
        "store_id": STORE_ID,
        "camera_id": "CAM1",
        "local_tracker_id": 42,
        "event_type": "ZONE_ENTER",
        "zone_id": "skincare",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "dwell_time_seconds": None,
        "bounding_box": [120.5, 340.2, 210.0, 520.1],
        "detection_confidence": 0.92,
        "visual_embedding": [0.1] * 512
    }
    
    try:
        response = httpx.post(f"{BASE_URL}/events/ingest", json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Payload: {response.json()}")
    except Exception as e:
        print(f"Error ingesting event: {e}")
        return

    # 3. Retrieve Metrics
    print("\n[3/5] Querying Store Conversion & Visitor Metrics...")
    try:
        response = httpx.get(f"{BASE_URL}/stores/{STORE_ID}/metrics")
        print(f"Status Code: {response.status_code}")
        print(f"Payload: {response.json()}")
    except Exception as e:
        print(f"Error fetching metrics: {e}")

    # 4. Funnel Report
    print("\n[4/5] Retrieving Retail Funnel Analysis...")
    try:
        response = httpx.get(f"{BASE_URL}/stores/{STORE_ID}/funnel")
        print(f"Status Code: {response.status_code}")
        print(f"Payload: {response.json()}")
    except Exception as e:
        print(f"Error fetching funnel: {e}")

    # 5. Density Heatmap
    print("\n[5/5] Fetching Spatial Coordinate Density Heatmap for CAM1...")
    try:
        response = httpx.get(f"{BASE_URL}/stores/{STORE_ID}/heatmap?camera_id=CAM1")
        print(f"Status Code: {response.status_code}")
        print(f"Payload: {response.json()}")
    except Exception as e:
        print(f"Error fetching heatmap: {e}")

    print("\n" + "=" * 60)
    print("VERIFICATION RUN COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    # Give server a moment in case it was just restarted
    time.sleep(1)
    test_api()
