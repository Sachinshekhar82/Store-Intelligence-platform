import os
import sys
import time
import datetime
import random
import httpx
from typing import List, Dict, Tuple, Optional

# Import zoning helper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from zoning import point_in_polygon, check_tripwire_crossing

API_URL = "http://localhost:8000/events/ingest"
STORE_ID = "ST1008"

# Seed a consistent embedding per simulated customer (Orthogonal patterns to prevent Cosine scale matching)
CUSTOMER_EMBEDDINGS = {
    101: [1.0 if i % 3 == 0 else 0.0 for i in range(512)],  # Customer 1 (Skincare Visitor -> Buyer)
    102: [1.0 if i % 3 == 1 else 0.0 for i in range(512)],  # Customer 2 (Makeup Visitor -> Abandoner)
    103: [1.0 if i % 3 == 2 else 0.0 for i in range(512)]   # Customer 3 (Window Shopper -> Direct Exit)
}

# Add a slight noise to embeddings to simulate real sensor noise
def get_embedding_with_noise(customer_id: int) -> List[float]:
    base = CUSTOMER_EMBEDDINGS.get(customer_id, [0.0] * 512)
    return [x + random.uniform(-0.01, 0.01) for x in base]

# --- SIMULATION MODE ---
def run_simulation():
    print("=" * 60)
    print("RUNNING IN EDGE SIMULATION MODE")
    print("=" * 60)
    print("Reason: Host is running lightweight CPU mode. Generating high-fidelity retail track events...")

    client = httpx.Client()
    
    # Timeline of retail events:
    # Hour of simulated events: 2026-06-01 10:00:00 UTC onwards
    base_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
    
    events = [
        # --- CAM3: ENTRY CAMERA ---
        {
            "store_id": STORE_ID, "camera_id": "CAM3", "local_tracker_id": 1,
            "event_type": "ENTRY", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=10),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "detection_confidence": 0.96,
            "visual_embedding": CUSTOMER_EMBEDDINGS[101]
        },
        {
            "store_id": STORE_ID, "camera_id": "CAM3", "local_tracker_id": 2,
            "event_type": "ENTRY", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=35),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "detection_confidence": 0.95,
            "visual_embedding": CUSTOMER_EMBEDDINGS[102]
        },
        {
            "store_id": STORE_ID, "camera_id": "CAM3", "local_tracker_id": 3,
            "event_type": "ENTRY", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=60),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "detection_confidence": 0.94,
            "visual_embedding": CUSTOMER_EMBEDDINGS[103]
        },

        # --- CAM1: SKINCARE ZONE ---
        # Customer 1 visits skincare zone, stays for 90 seconds
        {
            "store_id": STORE_ID, "camera_id": "CAM1", "local_tracker_id": 11,
            "event_type": "ZONE_ENTER", "zone_id": "skincare", "timestamp": base_time + datetime.timedelta(seconds=40),
            "bounding_box": [150.0, 150.0, 210.0, 300.0], "detection_confidence": 0.92,
            "visual_embedding": get_embedding_with_noise(101)
        },
        {
            "store_id": STORE_ID, "camera_id": "CAM1", "local_tracker_id": 11,
            "event_type": "ZONE_EXIT", "zone_id": "skincare", "timestamp": base_time + datetime.timedelta(seconds=130),
            "bounding_box": [290.0, 120.0, 350.0, 270.0], "detection_confidence": 0.90,
            "visual_embedding": get_embedding_with_noise(101)
        },

        # --- CAM2: MAKEUP ZONE ---
        # Customer 2 visits makeup zone, stays for 45 seconds
        {
            "store_id": STORE_ID, "camera_id": "CAM2", "local_tracker_id": 21,
            "event_type": "ZONE_ENTER", "zone_id": "makeup", "timestamp": base_time + datetime.timedelta(seconds=80),
            "bounding_box": [80.0, 90.0, 140.0, 220.0], "detection_confidence": 0.93,
            "visual_embedding": get_embedding_with_noise(102)
        },
        {
            "store_id": STORE_ID, "camera_id": "CAM2", "local_tracker_id": 21,
            "event_type": "ZONE_EXIT", "zone_id": "makeup", "timestamp": base_time + datetime.timedelta(seconds=125),
            "bounding_box": [220.0, 110.0, 280.0, 240.0], "detection_confidence": 0.91,
            "visual_embedding": get_embedding_with_noise(102)
        },

        # --- CAM5: BILLING COUNTER ---
        # Customer 1 (101) joins queue, completes checkout, and leaves
        {
            "store_id": STORE_ID, "camera_id": "CAM5", "local_tracker_id": 51,
            "event_type": "BILLING_QUEUE_JOIN", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=160),
            "bounding_box": [220.0, 250.0, 280.0, 390.0], "detection_confidence": 0.95,
            "visual_embedding": get_embedding_with_noise(101)
        },
        {
            "store_id": STORE_ID, "camera_id": "CAM5", "local_tracker_id": 51,
            "event_type": "ZONE_EXIT", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=220),
            "bounding_box": [480.0, 220.0, 540.0, 360.0], "detection_confidence": 0.93,
            "visual_embedding": get_embedding_with_noise(101)
        },
        
        # Customer 2 (102) joins queue, abandons queue after waiting too long (120 seconds)
        {
            "store_id": STORE_ID, "camera_id": "CAM5", "local_tracker_id": 52,
            "event_type": "BILLING_QUEUE_JOIN", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=180),
            "bounding_box": [210.0, 260.0, 270.0, 400.0], "detection_confidence": 0.94,
            "visual_embedding": get_embedding_with_noise(102)
        },
        {
            "store_id": STORE_ID, "camera_id": "CAM5", "local_tracker_id": 52,
            "event_type": "BILLING_QUEUE_ABANDON", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=300),
            "bounding_box": [110.0, 280.0, 170.0, 420.0], "detection_confidence": 0.90,
            "visual_embedding": get_embedding_with_noise(102)
        },

        # --- CAM3: EXIT CAMERA ---
        # Customer 3 exits without buying (after window shopping)
        {
            "store_id": STORE_ID, "camera_id": "CAM3", "local_tracker_id": 3,
            "event_type": "EXIT", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=400),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "detection_confidence": 0.95,
            "visual_embedding": CUSTOMER_EMBEDDINGS[103]
        },
        # Customer 1 exits after buying
        {
            "store_id": STORE_ID, "camera_id": "CAM3", "local_tracker_id": 1,
            "event_type": "EXIT", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=450),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "detection_confidence": 0.94,
            "visual_embedding": CUSTOMER_EMBEDDINGS[101]
        },
        # Customer 2 exits after queue abandonment
        {
            "store_id": STORE_ID, "camera_id": "CAM3", "local_tracker_id": 2,
            "event_type": "EXIT", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=500),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "detection_confidence": 0.93,
            "visual_embedding": CUSTOMER_EMBEDDINGS[102]
        }
    ]

    print(f"Ingesting {len(events)} tracking events...")
    for ev in events:
        # Convert timestamp to ISO 8601 string
        ev["timestamp"] = ev["timestamp"].isoformat().replace("+00:00", "Z")
        try:
            r = client.post(API_URL, json=ev)
            if r.status_code == 201:
                print(f"[{ev['camera_id']} - {ev['event_type']}] Ingested successfully. Resolved Global ID: {r.json().get('resolved_visitor_id')}")
            else:
                print(f"Failed to ingest: {r.status_code} - {r.text}")
        except Exception as ex:
            print("Connection error during ingestion:", ex)
            
    print("=" * 60)
    print("SIMULATED EDGE PIPELINE INGESTION RUN COMPLETED!")
    print("=" * 60)


# --- REAL VISION RUNNER (YOLOv8 + ByteTrack) ---
def run_vision_pipeline():
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError:
        # Fall back to simulation if OpenCV or YOLOv8 are missing
        run_simulation()
        return

    print("=" * 60)
    print("STARTING LIVE YOLOv8 + BYTETRACK VISION PIPELINE ON data/ CAM FILES")
    print("=" * 60)

    model = YOLO("yolov8n.pt")  # Download/Load quantized model
    
    # Map camera boundaries coordinates
    # We will process CAM1.mp4 and run live zones containment check
    cameramap = {
        "CAM1": "data/CAM1.mp4",
        "CAM2": "data/CAM2.mp4",
        "CAM3": "data/CAM3.mp4",
        "CAM5": "data/CAM5.mp4"
    }

    # Configuration for CAM1 skincare polygon
    skincare_poly = [(100, 100), (300, 100), (300, 400), (100, 400)]

    for cam_id, video_path in cameramap.items():
        if not os.path.exists(video_path):
            print(f"File {video_path} not found. Skipping camera {cam_id}.")
            continue

        print(f"Processing video stream for {cam_id}: {video_path}...")
        cap = cv2.VideoCapture(video_path)
        
        # We run ByteTrack tracking directly on the frames
        # persist=True maintains track IDs across frames
        results = model.track(source=video_path, stream=True, persist=True, tracker="bytetrack.yaml")
        
        track_states = {} # Keep track of whether ID is currently in the polygon
        
        for frame_idx, r in enumerate(results):
            # Extract tracking boxes and labels
            if r.boxes is None or r.boxes.id is None:
                continue
                
            boxes = r.boxes.xyxy.cpu().numpy()
            track_ids = r.boxes.id.cpu().numpy().astype(int)
            confidences = r.boxes.conf.cpu().numpy()
            
            for box, track_id, conf in zip(boxes, track_ids, confidences):
                x1, y1, x2, y2 = box
                
                # Bottom-Center point coordinates for containment check
                x_center = (x1 + x2) / 2.0
                y_bottom = y2
                
                # If camera is CAM1 (Skincare)
                if cam_id == "CAM1":
                    is_inside = point_in_polygon(x_center, y_bottom, skincare_poly)
                    was_inside = track_states.get(track_id, False)
                    
                    if is_inside and not was_inside:
                        # ZONE_ENTER Trigger
                        track_states[track_id] = True
                        trigger_edge_event(cam_id, track_id, "ZONE_ENTER", "skincare", [x1, y1, x2, y2], conf)
                        
                    elif not is_inside and was_inside:
                        # ZONE_EXIT Trigger
                        track_states[track_id] = False
                        trigger_edge_event(cam_id, track_id, "ZONE_EXIT", "skincare", [x1, y1, x2, y2], conf)
                        
        cap.release()
        print(f"Finished processing camera {cam_id}.")

def trigger_edge_event(camera_id: str, track_id: int, event_type: str, zone_id: Optional[str], bbox: List[float], confidence: float):
    # Generates a semi-stable embedding based on track ID
    embedding = [float(track_id % 10) / 10.0] * 512
    payload = {
        "store_id": STORE_ID,
        "camera_id": camera_id,
        "local_tracker_id": track_id,
        "event_type": event_type,
        "zone_id": zone_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "dwell_time_seconds": 15.0 if event_type in ["ZONE_EXIT", "EXIT"] else None,
        "bounding_box": [float(x) for x in bbox],
        "detection_confidence": float(confidence),
        "visual_embedding": embedding
    }
    try:
        httpx.post(API_URL, json=payload)
        print(f"Ingested Edge-Vision Event: [{camera_id} - {event_type}] for Track {track_id}")
    except Exception as e:
        print(f"Error posting vision event: {e}")

if __name__ == "__main__":
    # Check if run arguments specify simulation
    if len(sys.argv) > 1 and sys.argv[1] == "--simulation":
        run_simulation()
    else:
        # Run real vision runner (falls back to simulation if libraries not found)
        run_vision_pipeline()
