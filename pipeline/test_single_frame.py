import cv2
from ultralytics import YOLO
import os

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(project_dir, "yolov8n.pt")
model = YOLO(model_path)

video_path = os.path.join(project_dir, "data", "CAM1.mp4")
cap = cv2.VideoCapture(video_path)
ret, frame = cap.read()
cap.release()

if ret:
    print("Successfully read a frame.")
    results = model(frame, verbose=False, classes=[0])
    print(f"Results type: {type(results)}")
    for r in results:
        print(f"r.boxes: {r.boxes}")
        print(f"type(r.boxes): {type(r.boxes)}")
        if r.boxes is not None:
            print(f"r.boxes.xyxy: {r.boxes.xyxy}")
            print(f"len(r.boxes): {len(r.boxes)}")
            print(f"r.boxes.cls: {r.boxes.cls}")
else:
    print("Failed to read frame.")
