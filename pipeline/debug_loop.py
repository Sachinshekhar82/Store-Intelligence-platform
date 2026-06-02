import cv2
from ultralytics import YOLO
import os

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(project_dir, "yolov8n.pt")
model = YOLO(model_path)

video_path = os.path.join(project_dir, "data", "CAM1.mp4")
cap = cv2.VideoCapture(video_path)

frame_idx = 0
while cap.isOpened() and frame_idx < 50:
    ret, frame = cap.read()
    if not ret:
        break
        
    if frame_idx % 3 == 0:
        results = model(frame, verbose=False, classes=[0])
        total_detections = sum(len(r.boxes) for r in results if r.boxes is not None)
        print(f"Frame {frame_idx}: person detections = {total_detections}")
        
        if total_detections == 0:
            results = model(frame, verbose=False)
            all_detections = sum(len(r.boxes) for r in results if r.boxes is not None)
            print(f"  Ran general: detections = {all_detections}")
            for r in results:
                if r.boxes is not None and len(r.boxes) > 0:
                    print(f"  Classes found: {[model.names[int(c)] for c in r.boxes.cls.cpu().numpy()]}")
                    
    frame_idx += 1
cap.release()
