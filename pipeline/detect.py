import os
import sys
import json
import time
import cv2
from ultralytics import YOLO

def detect_persons(video_path: str, output_video_path: str, output_json_path: str):
    print("=" * 60)
    print("YOLOv8 PERSON DETECTION PIPELINE")
    print("=" * 60)
    
    if not os.path.exists(video_path):
        print(f"Error: Input video not found at {video_path}")
        sys.exit(1)
        
    print(f"Loading YOLOv8n model...")
    # Load the lightweight YOLOv8 nano model
    model = YOLO("yolov8n.pt")
    
    print(f"Opening video file: {video_path}")
    cap = cv2.VideoCapture(video_path)
    
    # Get video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print(f"Video Resolution: {width}x{height}")
    print(f"FPS: {fps:.2f} | Total Frames: {total_frames}")
    print("-" * 60)
    
    # Setup Video Writer for annotated output
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    
    detections_log = []
    frame_idx = 0
    start_time = time.time()
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_idx += 1
        
        # Run inference (stream mode for memory efficiency)
        # We specify device='cpu' to ensure universal compatibility, but it will use GPU if available
        results = model(frame, verbose=False)
        
        frame_detections = []
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                # Class index: 0 is 'person' in COCO dataset
                class_id = int(box.cls[0])
                if class_id != 0:
                    continue  # Filter out non-person classes
                    
                # Extract coordinates and confidence
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                
                # Record detection details
                detection_data = {
                    "box": [round(float(x1), 1), round(float(y1), 1), round(float(x2), 1), round(float(y2), 1)],
                    "confidence": round(conf, 4)
                }
                frame_detections.append(detection_data)
                
                # --- Drawing annotations ---
                # Draw bounding box (neon green)
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                
                # Draw label background
                label = f"Person: {conf:.1%}"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (int(x1), int(y1) - 20), (int(x1) + w, int(y1)), (0, 255, 0), -1)
                
                # Draw label text (black text on green background)
                cv2.putText(frame, label, (int(x1), int(y1) - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
                            
        # Log detections for this frame
        if frame_detections:
            detections_log.append({
                "frame": frame_idx,
                "timestamp_ms": round((frame_idx / fps) * 1000, 1),
                "detections": frame_detections
            })
            
        # Write annotated frame
        out.write(frame)
        
        # Progress logging
        if frame_idx % 30 == 0 or frame_idx == total_frames:
            elapsed = time.time() - start_time
            fps_speed = frame_idx / elapsed
            percent = (frame_idx / total_frames) * 100
            print(f"Processing: {percent:.1f}% ({frame_idx}/{total_frames} frames) | Speed: {fps_speed:.1f} FPS")

    cap.release()
    out.release()
    
    # Save detection logs to JSON
    with open(output_json_path, 'w') as f:
        json.dump({
            "video_metadata": {
                "source": os.path.basename(video_path),
                "resolution": f"{width}x{height}",
                "fps": round(fps, 2),
                "total_frames": total_frames
            },
            "frames_log": detections_log
        }, f, indent=2)
        
    total_time = time.time() - start_time
    print("-" * 60)
    print("DETECTION COMPLETE")
    print("-" * 60)
    print(f"Total time elapsed: {total_time:.2f} seconds")
    print(f"Average speed: {total_frames / total_time:.1f} FPS")
    print(f"Annotated video exported to: {output_video_path}")
    print(f"Detection logs exported to: {output_json_path}")
    print("=" * 60)

if __name__ == "__main__":
    input_file = "data/videos/STORE_BLR_001_ENTRY.mp4"
    output_file = "data/videos/STORE_BLR_001_ENTRY_annotated.mp4"
    json_log = "data/videos/detections.json"
    
    detect_persons(input_file, output_file, json_log)
