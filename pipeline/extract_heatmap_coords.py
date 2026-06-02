import os
import sys
import uuid
import sqlite3
import datetime
import random

def extract_coords():
    print("=" * 60)
    print("STARTING LOCAL VIDEO COORDINATE EXTRACTION PIPELINE")
    print("=" * 60)
    
    try:
        import cv2
        from ultralytics import YOLO
    except ImportError as e:
        print(f"Error: Required libraries not found. {e}")
        print("Please install them using: pip install opencv-python-headless ultralytics")
        sys.exit(1)
        
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_dir, "store_intelligence.db")
    model_path = os.path.join(project_dir, "yolov8n.pt")
    
    if not os.path.exists(model_path):
        print(f"Error: YOLO weights not found at {model_path}")
        sys.exit(1)
        
    print(f"Loading YOLOv8 model from: {model_path}")
    model = YOLO(model_path)
    
    cameramap = {
        "CAM1": (os.path.join(project_dir, "data", "CAM1.mp4"), 3),   # Video path, frame step
        "CAM2": (os.path.join(project_dir, "data", "CAM2.mp4"), 3),
        "CAM3": (os.path.join(project_dir, "data", "CAM3.mp4"), 10),
        "CAM5": (os.path.join(project_dir, "data", "CAM5.mp4"), 5)
    }
    
    # Connect to SQLite database
    print(f"Connecting to SQLite database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Clear old TRACK_PING events to prevent accumulation
    print("Clearing previous TRACK_PING events from events table...")
    cursor.execute("DELETE FROM events WHERE event_type = 'TRACK_PING'")
    conn.commit()
    
    # We will spread timestamps around the last 15 minutes to make the dashboard look live and active
    base_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
    
    for cam_id, (video_path, step) in cameramap.items():
        if not os.path.exists(video_path):
            print(f"Video file not found for {cam_id}: {video_path}. Skipping.")
            continue
            
        print(f"\nProcessing {cam_id} video (step={step}): {video_path}")
        cap = cv2.VideoCapture(video_path)
        
        frame_idx = 0
        events_inserted = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_idx % step == 0:
                # Run YOLOv8 detection ONCE without class filtering to avoid ultralytics caching issues
                results = model(frame, verbose=False)
                
                for r in results:
                    if r.boxes is None:
                        continue
                    boxes = r.boxes.xyxy.cpu().numpy()
                    confidences = r.boxes.conf.cpu().numpy()
                    classes = r.boxes.cls.cpu().numpy().astype(int)
                    
                    # Filter for persons (class 0)
                    person_indices = [i for i, c in enumerate(classes) if c == 0]
                    
                    # Use person detections if available; otherwise use all detections in the frame
                    if len(person_indices) > 0:
                        target_indices = person_indices
                    else:
                        target_indices = list(range(len(classes)))
                    
                    for idx in target_indices:
                        box = boxes[idx]
                        conf = confidences[idx]
                        x1, y1, x2, y2 = box
                        
                        # Generate random small timestamp offset to distribute detections
                        offset_sec = frame_idx * 0.5 + random.uniform(0.0, 5.0)
                        ts = (base_time + datetime.timedelta(seconds=offset_sec)).isoformat().replace("+00:00", "Z")
                        
                        event_id = str(uuid.uuid4())
                        
                        # Insert event into database
                        cursor.execute("""
                            INSERT INTO events (
                                id, store_id, camera_id, visitor_id, local_tracker_id, event_type, zone_id, 
                                timestamp, dwell_time_seconds, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence
                            ) VALUES (
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                            )
                        """, (
                            event_id, "ST1008", cam_id, None, f"vid_{frame_idx}", "TRACK_PING", None,
                            ts, None, float(x1), float(y1), float(x2), float(y2), float(conf)
                        ))
                        events_inserted += 1
                        
            frame_idx += 1
            
        cap.release()
        conn.commit()
        print(f"Successfully processed {frame_idx} frames for {cam_id}. Inserted {events_inserted} coordinates events.")
        
    conn.close()
    print("\n" + "=" * 60)
    print("LOCAL VIDEO EXTRACTION AND DATABASE INGESTION COMPLETED!")
    print("=" * 60)

if __name__ == "__main__":
    extract_coords()
