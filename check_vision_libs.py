import sys

try:
    import cv2
    import ultralytics
    with open("check_vision_libs.txt", "w") as f:
        f.write(f"cv2 version: {cv2.__version__}\n")
        f.write(f"ultralytics version: {ultralytics.__version__}\n")
except Exception as e:
    with open("check_vision_libs.txt", "w") as f:
        f.write(f"Error importing libraries: {e}\n")
