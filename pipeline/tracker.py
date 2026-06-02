import os
import sys
import csv
import time
import datetime
import cv2
from ultralytics import YOLO

class StoreTracker:
    def __init__(self, model_path: str = "yolov8n.pt"):
        print(f"Initializing YOLOv8 model from {model_path}...")
        # Load YOLOv8 model (Nano is optimal for CPU/Edge)
        self.model = YOLO(model_path)
        
    def track_camera_feed(self, video_path: str, output_video_path: str, export_csv_path: str):
        print("=" * 60)
        print("BYTETRACK OBJECT TRACKING PIPELINE")
        print("=" * 60)
        
        if not os.path.exists(video_path):
            print(f"Error: Input video not found at {video_path}")
            sys.exit(1)
            
        print(f"Opening video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        
        # Get video details
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"Resolution: {width}x{height} | FPS: {fps:.2f} | Total Frames: {total_frames}")
        
        # Setup Video Writer to output annotated tracked video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
        
        # Open CSV file to export trajectory results
        csv_file = open(export_csv_path, mode='w', newline='')
        csv_writer = csv.writer(csv_file)
        # Write headers
        csv_writer.writerow(["visitor_id", "timestamp", "bounding_box"])
        
        frame_idx = 0
        start_time = time.time()
        base_timestamp = datetime.datetime.now(datetime.timezone.utc)
        
        print("Processing frames using YOLOv8 + ByteTrack...")
        print("-" * 60)
        
        # Run tracking using ByteTrack
        # stream=True processes frame-by-frame efficiently without loading whole video into memory
        # persist=True keeps tracking IDs active across frames
        results = self.model.track(
            source=video_path,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],  # Class index 0 is 'person' in COCO (ignores other classes automatically)
            verbose=False,
            stream=True
        )
        
        for r in results:
            frame_idx += 1
            
            # Read frame to apply manual visual annotations
            ret, frame = cap.read()
            if not ret:
                break
                
            # If no boxes are detected in this frame, write frame and continue
            if r.boxes is None or r.boxes.id is None:
                out.write(frame)
                continue
                
            # Get track details
            boxes = r.boxes.xyxy.cpu().numpy()  # coordinates
            track_ids = r.boxes.id.cpu().numpy().astype(int)  # persistent tracking IDs
            confidences = r.boxes.conf.cpu().numpy()  # detection confidences
            
            # Formulate the elapsed timestamp for this frame
            elapsed_seconds = frame_idx / fps
            frame_time = base_timestamp + datetime.timedelta(seconds=elapsed_seconds)
            timestamp_str = frame_time.isoformat().replace("+00:00", "Z")
            
            for box, track_id, conf in zip(boxes, track_ids, confidences):
                x1, y1, x2, y2 = box
                
                # Format bounding box as array string: [x1, y1, x2, y2]
                bbox_str = f"[{round(float(x1),1)},{round(float(y1),1)},{round(float(x2),1)},{round(float(y2),1)}]"
                
                # Export record to CSV
                csv_writer.writerow([track_id, timestamp_str, bbox_str])
                
                # --- Drawing annotations ---
                # Unique color per track (using hash of track ID)
                # Cast elements to standard Python ints to avoid OpenCV type-parsing errors
                color_r = int((track_id * 37) % 255)
                color_g = int((track_id * 73) % 255)
                color_b = int((track_id * 113) % 255)
                box_color = (color_b, color_g, color_r)
                
                # Draw bounding box
                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), box_color, 2)
                
                # Draw track ID label
                label = f"Visitor {track_id} ({conf:.0%})"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(frame, (int(x1), int(y1) - 20), (int(x1) + w, int(y1)), box_color, -1)
                cv2.putText(frame, label, (int(x1), int(y1) - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
            
            # Write annotated frame
            out.write(frame)
            
            # Log progress
            if frame_idx % 30 == 0 or frame_idx == total_frames:
                elapsed = time.time() - start_time
                speed = frame_idx / elapsed
                percent = (frame_idx / total_frames) * 100
                print(f"Tracking: {percent:.1f}% ({frame_idx}/{total_frames} frames) | Speed: {speed:.1f} FPS")
                
        # Clean up
        cap.release()
        out.release()
        csv_file.close()
        
        total_time = time.time() - start_time
        print("-" * 60)
        print("TRACKING COMPLETED SUCCESSFULLY")
        print("-" * 60)
        print(f"Total time elapsed: {total_time:.2f} seconds")
        print(f"Average speed: {total_frames / total_time:.1f} FPS")
        print(f"Tracked video exported to: {output_video_path}")
        print(f"Trajectory log exported to: {export_csv_path}")
        print("=" * 60)

if __name__ == "__main__":
    # Settings for default input files
    input_video = "data/videos/STORE_BLR_001_ENTRY.mp4"
    output_video = "data/videos/STORE_BLR_001_ENTRY_tracked.mp4"
    trajectory_csv = "data/videos/trajectories.csv"
    
    tracker = StoreTracker()
    tracker.track_camera_feed(input_video, output_video, trajectory_csv)
