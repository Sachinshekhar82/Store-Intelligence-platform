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

# Post to both local FastAPI server and public Render API
API_URLS = [
    "http://localhost:8000/events/ingest",
    "https://store-intelligence-platform.onrender.com/events/ingest"
]
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
    print("RUNNING RICH EDGE SIMULATION FOR BOTH SERVERS")
    print("=" * 60)

    # Hour of simulated events: 2026-06-01 10:00:00 UTC onwards
    base_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
    
    story_events = [
        # --- CAM3: ENTRY CAMERA ---
        {
            "camera_id": "CAM3", "local_tracker_id": 1,
            "event_type": "ENTRY", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=10),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "visual_embedding": CUSTOMER_EMBEDDINGS[101]
        },
        {
            "camera_id": "CAM3", "local_tracker_id": 2,
            "event_type": "ENTRY", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=35),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "visual_embedding": CUSTOMER_EMBEDDINGS[102]
        },
        {
            "camera_id": "CAM3", "local_tracker_id": 3,
            "event_type": "ENTRY", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=60),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "visual_embedding": CUSTOMER_EMBEDDINGS[103]
        },

        # --- CAM1: SKINCARE ZONE ---
        # Customer 1 visits skincare zone, stays for 90 seconds
        {
            "camera_id": "CAM1", "local_tracker_id": 11,
            "event_type": "ZONE_ENTER", "zone_id": "skincare", "timestamp": base_time + datetime.timedelta(seconds=40),
            "bounding_box": [120.0, 130.0, 140.0, 170.0], "visual_embedding": get_embedding_with_noise(101)
        },
        {
            "camera_id": "CAM1", "local_tracker_id": 11,
            "event_type": "ZONE_EXIT", "zone_id": "skincare", "timestamp": base_time + datetime.timedelta(seconds=130),
            "bounding_box": [140.0, 110.0, 160.0, 150.0], "visual_embedding": get_embedding_with_noise(101)
        },

        # --- CAM2: MAKEUP ZONE ---
        # Customer 2 visits makeup zone, stays for 45 seconds
        {
            "camera_id": "CAM2", "local_tracker_id": 21,
            "event_type": "ZONE_ENTER", "zone_id": "makeup", "timestamp": base_time + datetime.timedelta(seconds=80),
            "bounding_box": [270.0, 220.0, 290.0, 260.0], "visual_embedding": get_embedding_with_noise(102)
        },
        {
            "camera_id": "CAM2", "local_tracker_id": 21,
            "event_type": "ZONE_EXIT", "zone_id": "makeup", "timestamp": base_time + datetime.timedelta(seconds=125),
            "bounding_box": [290.0, 230.0, 310.0, 270.0], "visual_embedding": get_embedding_with_noise(102)
        },

        # --- CAM5: BILLING COUNTER ---
        # Customer 1 (101) joins queue, completes checkout, and leaves
        {
            "camera_id": "CAM5", "local_tracker_id": 51,
            "event_type": "BILLING_QUEUE_JOIN", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=160),
            "bounding_box": [490.0, 380.0, 510.0, 420.0], "visual_embedding": get_embedding_with_noise(101)
        },
        {
            "camera_id": "CAM5", "local_tracker_id": 51,
            "event_type": "ZONE_EXIT", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=220),
            "bounding_box": [510.0, 390.0, 530.0, 430.0], "visual_embedding": get_embedding_with_noise(101)
        },
        
        # Customer 2 (102) joins queue, abandons queue after waiting too long (120 seconds)
        {
            "camera_id": "CAM5", "local_tracker_id": 52,
            "event_type": "BILLING_QUEUE_JOIN", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=180),
            "bounding_box": [500.0, 370.0, 520.0, 410.0], "visual_embedding": get_embedding_with_noise(102)
        },
        {
            "camera_id": "CAM5", "local_tracker_id": 52,
            "event_type": "BILLING_QUEUE_ABANDON", "zone_id": "billing_queue", "timestamp": base_time + datetime.timedelta(seconds=300),
            "bounding_box": [480.0, 400.0, 500.0, 440.0], "visual_embedding": get_embedding_with_noise(102)
        },

        # --- CAM3: EXIT CAMERA ---
        # Customer 3 exits without buying (after window shopping)
        {
            "camera_id": "CAM3", "local_tracker_id": 3,
            "event_type": "EXIT", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=400),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "visual_embedding": CUSTOMER_EMBEDDINGS[103]
        },
        # Customer 1 exits after buying
        {
            "camera_id": "CAM3", "local_tracker_id": 1,
            "event_type": "EXIT", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=450),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "visual_embedding": CUSTOMER_EMBEDDINGS[101]
        },
        # Customer 2 exits after queue abandonment
        {
            "camera_id": "CAM3", "local_tracker_id": 2,
            "event_type": "EXIT", "zone_id": None, "timestamp": base_time + datetime.timedelta(seconds=500),
            "bounding_box": [320.0, 400.0, 380.0, 480.0], "visual_embedding": CUSTOMER_EMBEDDINGS[102]
        }
    ]

    print(f"Ingesting {len(story_events)} core retail funnel events...")
    for ev in story_events:
        ts_str = ev["timestamp"].isoformat().replace("+00:00", "Z")
        trigger_edge_event(
            ev["camera_id"], ev["local_tracker_id"], ev["event_type"], 
            ev["zone_id"], ev["bounding_box"], 0.95, ts_str
        )

    # Generate a large number of scattered coordinates for accurate heatmaps (50 points per camera)
    print("\nGenerating dense coordinate tracking events for highly accurate heatmaps...")
    for cam_id in ["CAM1", "CAM2", "CAM3", "CAM5"]:
        for i in range(50):
            if cam_id == "CAM1":    # Skincare Zone bounds
                x = random.uniform(110.0, 160.0)
                y = random.uniform(120.0, 170.0)
            elif cam_id == "CAM2":  # Makeup Zone bounds
                x = random.uniform(260.0, 320.0)
                y = random.uniform(215.0, 270.0)
            elif cam_id == "CAM3":  # Entry/Exit bounds
                x = random.uniform(75.0, 110.0)
                y = random.uniform(220.0, 260.0)
            else:                   # CAM5: Billing Queue bounds
                x = random.uniform(480.0, 545.0)
                y = random.uniform(380.0, 410.0)

            # bbox: [x1, y1, x2, y2] designed so that (x1+x2)/2 = x and (y1+y2)/2 = y
            bbox = [x - 10.0, y - 10.0, x + 10.0, y + 10.0]
            offset_seconds = random.randint(0, 600)
            ts = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=offset_seconds)).isoformat().replace("+00:00", "Z")
            
            trigger_edge_event(
                cam_id, 999 + i, "TRACK_PING", None, bbox, 0.90, ts
            )

    print("=" * 60)
    print("SIMULATED EDGE PIPELINE INGESTION RUN COMPLETED FOR BOTH SERVERS!")
    print("=" * 60)


# --- REAL VISION RUNNER (YOLOv8 + ByteTrack) ---
def run_vision_pipeline():
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError:
        # Fall back to simulation if OpenCV or YOLOv8 are missing
        print("Vision libraries (OpenCV / Ultralytics) not found. Falling back to simulation...")
        run_simulation()
        return

    print("=" * 60)
    print("STARTING LIVE YOLOv8 + BYTETRACK VISION PIPELINE ON data/ CAM FILES")
    print("=" * 60)

    # Load quantized weights
    model = YOLO("yolov8n.pt")
    
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
        
        # Run ByteTrack tracking directly on the frames
        # persist=True maintains track IDs across frames
        results = model.track(source=video_path, stream=True, persist=True, tracker="bytetrack.yaml")
        
        track_states = {} # Keep track of whether ID is currently in the polygon
        
        for frame_idx, r in enumerate(results):
            # Limit processing to first 100 frames to run quickly on CPU
            if frame_idx >= 100:
                break
                
            if r.boxes is None or r.boxes.id is None:
                continue
                
            boxes = r.boxes.xyxy.cpu().numpy()
            track_ids = r.boxes.id.cpu().numpy().astype(int)
            confidences = r.boxes.conf.cpu().numpy()
            
            # Send periodic tracker coordinates pings to generate dense heatmaps
            if frame_idx % 10 == 0:
                for box, track_id, conf in zip(boxes, track_ids, confidences):
                    x1, y1, x2, y2 = box
                    trigger_edge_event(cam_id, track_id, "TRACK_PING", None, [x1, y1, x2, y2], conf)
            
            # Perform boundary containment for zone analysis
            for box, track_id, conf in zip(boxes, track_ids, confidences):
                x1, y1, x2, y2 = box
                x_center = (x1 + x2) / 2.0
                y_bottom = y2
                
                if cam_id == "CAM1":
                    is_inside = point_in_polygon(x_center, y_bottom, skincare_poly)
                    was_inside = track_states.get(track_id, False)
                    
                    if is_inside and not was_inside:
                        track_states[track_id] = True
                        trigger_edge_event(cam_id, track_id, "ZONE_ENTER", "skincare", [x1, y1, x2, y2], conf)
                    elif not is_inside and was_inside:
                        track_states[track_id] = False
                        trigger_edge_event(cam_id, track_id, "ZONE_EXIT", "skincare", [x1, y1, x2, y2], conf)
                        
        cap.release()
        print(f"Finished processing camera {cam_id}.")

def trigger_edge_event(camera_id: str, track_id: int, event_type: str, zone_id: Optional[str], bbox: List[float], confidence: float, timestamp: Optional[str] = None):
    # Generates a semi-stable embedding based on track ID
    embedding = [float(track_id % 10) / 10.0] * 512
    if not timestamp:
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
        
    payload = {
        "store_id": STORE_ID,
        "camera_id": camera_id,
        "local_tracker_id": track_id,
        "event_type": event_type,
        "zone_id": zone_id,
        "timestamp": timestamp,
        "dwell_time_seconds": 15.0 if event_type in ["ZONE_EXIT", "EXIT"] else None,
        "bounding_box": [float(x) for x in bbox],
        "detection_confidence": float(confidence),
        "visual_embedding": embedding
    }
    
    # Send events to both API endpoints
    for url in API_URLS:
        try:
            r = httpx.post(url, json=payload, timeout=2.0)
            if r.status_code in [200, 201]:
                print(f"Ingested Edge Event to {url}: [{camera_id} - {event_type}] for Track {track_id}")
            else:
                print(f"Failed to ingest to {url}: Status {r.status_code} - {r.text}")
        except Exception as e:
            # Silent print to avoid console clutter if server is offline
            print(f"Connection warning to {url}: {e}")

if __name__ == "__main__":
    # Check if run arguments specify simulation
    if len(sys.argv) > 1 and sys.argv[1] == "--simulation":
        run_simulation()
    else:
        # Run real vision runner (falls back to simulation if libraries not found)
        run_vision_pipeline()
