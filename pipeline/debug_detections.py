import cv2
from ultralytics import YOLO
import os

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(project_dir, "yolov8n.pt")
model = YOLO(model_path)

cameramap = {
    "CAM1": os.path.join(project_dir, "data", "CAM1.mp4"),
    "CAM2": os.path.join(project_dir, "data", "CAM2.mp4"),
    "CAM3": os.path.join(project_dir, "data", "CAM3.mp4"),
    "CAM5": os.path.join(project_dir, "data", "CAM5.mp4")
}

with open("scratch/debug_detections.txt", "w") as f:
    for cam_id, video_path in cameramap.items():
        f.write(f"\n=================== {cam_id} ===================\n")
        if not os.path.exists(video_path):
            f.write("Video file not found.\n")
            continue
            
        cap = cv2.VideoCapture(video_path)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        f.write(f"Total frames: {frame_count}\n")
        
        # Check first 50 frames
        detected_classes = {}
        detected_boxes_count = 0
        
        for idx in range(min(50, frame_count)):
            ret, frame = cap.read()
            if not ret:
                break
                
            results = model(frame, verbose=False)
            for r in results:
                if r.boxes is not None:
                    cls = r.boxes.cls.cpu().numpy()
                    conf = r.boxes.conf.cpu().numpy()
                    detected_boxes_count += len(cls)
                    for c, co in zip(cls, conf):
                        name = model.names[int(c)]
                        detected_classes[name] = detected_classes.get(name, 0) + 1
                        
        f.write(f"First 50 frames: Total detections = {detected_boxes_count}\n")
        f.write(f"Classes: {detected_classes}\n")
        cap.release()
