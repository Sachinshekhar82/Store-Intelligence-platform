import cv2
from ultralytics import YOLO
import os

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(project_dir, "yolov8n.pt")
model = YOLO(model_path)

video_path = os.path.join(project_dir, "data", "CAM1.mp4")
cap = cv2.VideoCapture(video_path)

frame_idx = 0
total_events = 0
person_events = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
        
    if frame_idx % 15 == 0:
        results = model(frame, verbose=False, classes=[0])
        person_count = sum(len(r.boxes) for r in results if r.boxes is not None)
        
        # Run general
        results_all = model(frame, verbose=False)
        all_count = sum(len(r.boxes) for r in results_all if r.boxes is not None)
        
        print(f"Frame {frame_idx}: person={person_count}, all={all_count}")
        total_events += all_count
        person_events += person_count
        
    frame_idx += 1
    
cap.release()
print(f"Summary: processed={frame_idx}, total_events={total_events}, person_events={person_events}")
