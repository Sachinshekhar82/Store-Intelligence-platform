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

# --- Geometry Helper ---

def point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
    """
    Ray-casting algorithm to determine if point (x, y) is inside a polygon.
    """
    n = len(polygon)
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


class ZoneAnalyzer:
    def __init__(self, camera_id: str, zone_id: str, polygon: List[Tuple[float, float]], store_id: str = "ST1008"):
        """
        camera_id: e.g., 'CAM1', 'CAM2', 'CAM5'
        zone_id: e.g., 'skincare', 'makeup', 'billing_queue'
        polygon: List of vertices defining the zone boundaries
        """
        self.camera_id = camera_id
        self.zone_id = zone_id
        self.polygon = polygon
        self.store_id = store_id
        
        # State tracking: track_id -> entry_timestamp (iso string)
        # Tracks visitors currently inside the zone to calculate dwell time on exit
        self.inside_state: Dict[int, str] = {}

    def get_bottom_center(self, bbox_str: str) -> Tuple[float, float]:
        """
        Parses bounding box string "[x1,y1,x2,y2]" and returns bottom-center coordinate.
        """
        bbox = json.loads(bbox_str)
        x1, y1, x2, y2 = bbox
        x_center = (x1 + x2) / 2.0
        y_bottom = y2
        return (x_center, y_bottom)

    def analyze_position(self, track_id: int, curr_pos: Tuple[float, float], timestamp: str) -> Optional[Tuple[str, Optional[float]]]:
        """
        Registers track position and checks containment transitions.
        Returns: Tuple (event_type, dwell_time_seconds) or None
        """
        is_inside = point_in_polygon(curr_pos[0], curr_pos[1], self.polygon)
        was_inside = track_id in self.inside_state
        
        if is_inside and not was_inside:
            # ZONE_ENTER Transition
            self.inside_state[track_id] = timestamp
            return "ZONE_ENTER", None
            
        elif not is_inside and was_inside:
            # ZONE_EXIT Transition
            entry_time_str = self.inside_state.pop(track_id)
            
            # Calculate Dwell Time
            try:
                # Parse ISO timestamps
                t_entry = datetime.datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
                t_exit = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                dwell_time = (t_exit - t_entry).total_seconds()
            except Exception:
                dwell_time = 0.0
                
            return "ZONE_EXIT", round(dwell_time, 2)
            
        return None

    def process_trajectories(self, csv_path: str) -> List[Dict]:
        """
        Reads a trajectories CSV log file and processes zone containment events.
        """
        detected_events = []
        if not os.path.exists(csv_path):
            print(f"Error: Trajectory log {csv_path} not found.")
            return detected_events
            
        print(f"Processing camera {self.camera_id} tracks in zone '{self.zone_id}' from {csv_path}...")
        
        with open(csv_path, mode='r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                track_id = int(row["visitor_id"])
                timestamp = row["timestamp"]
                bbox_str = row["bounding_box"]
                
                curr_pos = self.get_bottom_center(bbox_str)
                transition = self.analyze_position(track_id, curr_pos, timestamp)
                
                if transition:
                    event_type, dwell_time = transition
                    
                    # Map event types to billing specifics if on CAM5
                    mapped_event_type = event_type
                    if self.camera_id == "CAM5" and self.zone_id == "billing_queue":
                        if event_type == "ZONE_ENTER":
                            mapped_event_type = "BILLING_QUEUE_JOIN"
                        elif event_type == "ZONE_EXIT":
                            # For simple demo: assume exit from queue is exit (we check transactions separately)
                            mapped_event_type = "ZONE_EXIT"
                            
                    event = {
                        "store_id": self.store_id,
                        "camera_id": self.camera_id,
                        "local_tracker_id": track_id,
                        "event_type": mapped_event_type,
                        "zone_id": self.zone_id,
                        "timestamp": timestamp,
                        "dwell_time_seconds": dwell_time,
                        "bounding_box": json.loads(bbox_str),
                        "detection_confidence": 0.95
                    }
                    detected_events.append(event)
                    dwell_str = f" (Dwell: {dwell_time}s)" if dwell_time else ""
                    print(f"[{timestamp}] Triggered {mapped_event_type} for Visitor {track_id} in {self.zone_id}{dwell_str}")
                    
        return detected_events

    def send_events(self, events: List[Dict]):
        """
        Transmits the detected zone events to the cloud FastAPI ingestion gateway.
        """
        print("-" * 60)
        print(f"Sending {len(events)} zone events to Ingestion API...")
        client = httpx.Client()
        success = 0
        for ev in events:
            try:
                r = client.post(API_URL, json=ev)
                if r.status_code == 201:
                    success += 1
                else:
                    print(f"Failed: {r.status_code} - {r.text}")
            except Exception as e:
                print(f"Error connecting to backend: {e}")
        print(f"Successfully ingested {success}/{len(events)} zone events.")
        print("-" * 60)


# --- Unit Tests ---

class TestZoneAnalysis(unittest.TestCase):
    def setUp(self):
        # 100x100 rectangular polygon zone
        self.polygon = [(100, 100), (200, 100), (200, 200), (100, 200)]
        self.analyzer = ZoneAnalyzer("CAM1", "skincare", self.polygon)

    def test_zone_entry(self):
        """
        Verify walking inside polygon triggers ZONE_ENTER.
        """
        # (150, 150) is inside
        res = self.analyzer.analyze_position(1, (150, 150), "2026-06-02T10:00:00Z")
        self.assertIsNotNone(res)
        self.assertEqual(res[0], "ZONE_ENTER")
        self.assertIsNone(res[1])

    def test_zone_exit_and_dwell(self):
        """
        Verify exiting polygon triggers ZONE_EXIT and computes correct dwell time.
        """
        # Enter at 10:00:00
        self.analyzer.analyze_position(2, (150, 150), "2026-06-02T10:00:00Z")
        
        # Exit at 10:00:15 (15 seconds later)
        # (250, 250) is outside
        res = self.analyzer.analyze_position(2, (250, 250), "2026-06-02T10:00:15Z")
        self.assertIsNotNone(res)
        self.assertEqual(res[0], "ZONE_EXIT")
        self.assertEqual(res[1], 15.0)

    def test_duplicate_events(self):
        """
        Verify remaining inside does not trigger duplicate enter events.
        """
        self.assertEqual(self.analyzer.analyze_position(3, (150, 150), "2026-06-02T10:00:00Z")[0], "ZONE_ENTER")
        self.assertIsNone(self.analyzer.analyze_position(3, (160, 160), "2026-06-02T10:00:05Z"))


# --- Example Configuration & Main Run ---

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.argv.pop(1)
        unittest.main()
    else:
        # Example Setup Configuration
        # Target camera CAM1 Skincare. Polygon mapped to 4K video resolution
        skincare_poly = [(600, 600), (1800, 600), (1800, 2400), (600, 2400)]
        
        analyzer = ZoneAnalyzer(
            camera_id="CAM1",
            zone_id="skincare",
            polygon=skincare_poly,
            store_id=STORE_ID
        )
        
        # Mapped local trajectories file
        trajectory_log = "data/videos/trajectories.csv"
        events = analyzer.process_trajectories(trajectory_log)
        
        if events:
            analyzer.send_events(events)
        else:
            print("No zone transition events detected.")
