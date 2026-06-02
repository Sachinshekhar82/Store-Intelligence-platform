import cv2
from ultralytics import YOLO
import os

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(project_dir, "yolov8n.pt")
model = YOLO(model_path)

video_path = os.path.join(project_dir, "data", "CAM1.mp4")
cap = cv2.VideoCapture(video_path)

frame_idx = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    
    results = model(frame, verbose=False)
    for r in results:
        if r.boxes is not None and len(r.boxes) > 0:
            cls = r.boxes.cls.cpu().numpy()
            names = [model.names[int(c)] for c in cls]
            print(f"Frame {frame_idx} has detections: {names}")
            
    frame_idx += 1
cap.release()
