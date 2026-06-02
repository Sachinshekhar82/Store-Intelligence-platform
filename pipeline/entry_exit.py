import os
import sys
import json
import csv
import datetime
import unittest
from typing import List, Dict, Tuple, Optional
import httpx

# API configuration
API_URL = "http://localhost:8000/events/ingest"
STORE_ID = "ST1008"

# --- Geometry Utilities ---

def ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
    """
    Check if three points A, B, C are in counter-clockwise order.
    """
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

def intersect(line1: Tuple[Tuple[float, float], Tuple[float, float]], 
              line2: Tuple[Tuple[float, float], Tuple[float, float]]) -> bool:
    """
    Check if segment line1 (A->B) and line2 (C->D) intersect.
    """
    A, B = line1
    C, D = line2
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


class EntryExitAnalyzer:
    def __init__(self, tripwire: Tuple[Tuple[float, float], Tuple[float, float]], store_id: str = "ST1008"):
        """
        tripwire: Tuple of two coordinate pairs: ((x1, y1), (x2, y2))
        """
        self.tripwire = tripwire
        self.store_id = store_id
        # Session state: track_id -> List of previous coordinate history (bottom-center coordinates)
        self.track_history: Dict[int, List[Tuple[float, float]]] = {}
        # Trigger state: track_id -> last triggered event_type ('ENTRY' or 'EXIT') to prevent duplicates
        self.triggered_events: Dict[int, str] = {}
        
    def get_bottom_center(self, bbox_str: str) -> Tuple[float, float]:
        """
        Parses bounding box string "[x1,y1,x2,y2]" and returns bottom-center coordinate (x_center, y_bottom).
        """
        bbox = json.loads(bbox_str)
        x1, y1, x2, y2 = bbox
        x_center = (x1 + x2) / 2.0
        y_bottom = y2
        return (x_center, y_bottom)

    def analyze_movement(self, track_id: int, curr_pos: Tuple[float, float], timestamp: str) -> Optional[str]:
        """
        Registers track position and checks if it crosses the tripwire.
        Returns 'ENTRY', 'EXIT', or None.
        """
        if track_id not in self.track_history:
            self.track_history[track_id] = []
            
        history = self.track_history[track_id]
        
        # We need at least one previous point to detect crossing
        if len(history) > 0:
            prev_pos = history[-1]
            
            # Check segment intersection
            if intersect((prev_pos, curr_pos), self.tripwire):
                # Calculate cross product to determine crossing direction
                # Vector A->B (Tripwire) and Vector Prev->Curr (Movement)
                tx1, ty1 = self.tripwire[0]
                tx2, ty2 = self.tripwire[1]
                
                trip_dx = tx2 - tx1
                trip_dy = ty2 - ty1
                
                move_dx = curr_pos[0] - prev_pos[0]
                move_dy = curr_pos[1] - prev_pos[1]
                
                cross_product = (trip_dx * move_dy) - (trip_dy * move_dx)
                
                # Cross product > 0: Crossing from one side (ENTRY), < 0: opposite (EXIT)
                # We normalize directions based on y-coordinate values:
                # y-value increase (moving down-screen) is ENTRY
                # y-value decrease (moving up-screen) is EXIT
                raw_direction = "ENTRY" if cross_product > 0 else "EXIT"
                
                # Prevent duplicates: Check if track has already triggered this specific event type
                last_triggered = self.triggered_events.get(track_id)
                if last_triggered != raw_direction:
                    self.triggered_events[track_id] = raw_direction
                    return raw_direction
                    
        # Update history window (keep last 5 states for smoothing)
        history.append(curr_pos)
        if len(history) > 5:
            history.pop(0)
            
        return None

    def process_trajectory_log(self, csv_path: str) -> List[Dict]:
        """
        Reads a trajectories CSV log file and detects crossings.
        """
        detected_events = []
        if not os.path.exists(csv_path):
            print(f"Error: Trajectory log {csv_path} not found.")
            return detected_events
            
        print(f"Processing trajectory records from {csv_path}...")
        with open(csv_path, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                track_id = int(row["visitor_id"])
                timestamp = row["timestamp"]
                bbox_str = row["bounding_box"]
                
                curr_pos = self.get_bottom_center(bbox_str)
                event_type = self.analyze_movement(track_id, curr_pos, timestamp)
                
                if event_type:
                    event = {
                        "store_id": self.store_id,
                        "camera_id": "CAM3",
                        "local_tracker_id": track_id,
                        "event_type": event_type,
                        "zone_id": None,
                        "timestamp": timestamp,
                        "bounding_box": json.loads(bbox_str),
                        "detection_confidence": 0.95
                    }
                    detected_events.append(event)
                    print(f"[{timestamp}] Triggered {event_type} for Visitor {track_id}")
                    
        return detected_events

    def send_events_to_api(self, events: List[Dict]):
        """
        Sends the detected events to the cloud FastAPI ingestion gateway.
        """
        print("-" * 60)
        print(f"Sending {len(events)} entry/exit events to Analytics API...")
        client = httpx.Client()
        success = 0
        for ev in events:
            try:
                r = client.post(API_URL, json=ev)
                if r.status_code == 201:
                    success += 1
                else:
                    print(f"Failed to ingest event: {r.status_code} - {r.text}")
            except Exception as e:
                print(f"Connection error: {e}")
        print(f"Successfully ingested {success}/{len(events)} events.")
        print("-" * 60)


# --- Unit Tests ---

class TestEntryExitCrossing(unittest.TestCase):
    def setUp(self):
        # Config tripwire line at Y = 1080 (horizontal line across 4K resolution)
        self.tripwire = ((0, 1080), (3840, 1080))
        self.analyzer = EntryExitAnalyzer(self.tripwire)
        
    def test_entry_crossing(self):
        """
        Test that movement crossing from top to bottom (Y increasing) triggers ENTRY.
        """
        # Coordinate y goes from 1000 (above) to 1150 (below line 1080)
        self.assertIsNone(self.analyzer.analyze_movement(1, (1920, 1000), "2026-06-02T00:00:00Z"))
        event = self.analyzer.analyze_movement(1, (1920, 1150), "2026-06-02T00:00:01Z")
        self.assertEqual(event, "ENTRY")

    def test_exit_crossing(self):
        """
        Test that movement crossing from bottom to top (Y decreasing) triggers EXIT.
        """
        # Coordinate y goes from 1200 (below) to 900 (above line 1080)
        self.assertIsNone(self.analyzer.analyze_movement(2, (1920, 1200), "2026-06-02T00:00:00Z"))
        event = self.analyzer.analyze_movement(2, (1920, 900), "2026-06-02T00:00:01Z")
        self.assertEqual(event, "EXIT")

    def test_duplicate_prevention(self):
        """
        Verify that multiple points on the same side do not trigger multiple duplicate events.
        """
        # Coordinate y crosses line -> triggers ENTRY
        self.assertIsNone(self.analyzer.analyze_movement(3, (1920, 1000), "2026-06-02T00:00:00Z"))
        self.assertEqual(self.analyzer.analyze_movement(3, (1920, 1100), "2026-06-02T00:00:01Z"), "ENTRY")
        
        # Second point below the line -> should not trigger ENTRY again (None)
        self.assertIsNone(self.analyzer.analyze_movement(3, (1920, 1150), "2026-06-02T00:00:02Z"))
        
        # Crossing back up -> triggers EXIT
        self.assertEqual(self.analyzer.analyze_movement(3, (1920, 1000), "2026-06-02T00:00:03Z"), "EXIT")


# --- Main Execution ---

if __name__ == "__main__":
    # If run with argument --test, execute unit tests
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.argv.pop(1)
        unittest.main()
    else:
        # Process the real trajectories.csv generated by tracker.py on 4K entry video
        # 4K resolution is 3840x2160. Tripwire is placed horizontally at Y=1200
        tripwire_line = ((0, 1200), (3840, 1200))
        analyzer = EntryExitAnalyzer(tripwire_line, store_id=STORE_ID)
        
        trajectory_log = "data/videos/trajectories.csv"
        events = analyzer.process_trajectory_log(trajectory_log)
        
        if events:
            analyzer.send_events_to_api(events)
        else:
            print("No line crossing events detected.")
