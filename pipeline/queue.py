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


class QueueAnalyzer:
    def __init__(self, polygon: List[Tuple[float, float]], spike_threshold: int = 3, store_id: str = "ST1008"):
        self.polygon = polygon
        self.spike_threshold = spike_threshold
        self.store_id = store_id
        
        # Session state: track_id -> entry_timestamp (iso string)
        self.active_queue: Dict[int, str] = {}
        # Track last coordinates to determine exit direction
        self.last_coordinates: Dict[int, Tuple[float, float]] = {}
        # Spike tracking state to prevent duplicate spike alerts
        self.spike_alert_active = False

    def get_bottom_center(self, bbox_str: str) -> Tuple[float, float]:
        bbox = json.loads(bbox_str)
        x1, y1, x2, y2 = bbox
        x_center = (x1 + x2) / 2.0
        y_bottom = y2
        return (x_center, y_bottom)

    def update_track(self, track_id: int, curr_pos: Tuple[float, float], timestamp: str) -> List[Dict]:
        """
        Processes new track coordinates.
        Returns a list of triggered event dictionaries (JOIN, ABANDON, SPIKE).
        """
        events = []
        is_inside = point_in_polygon(curr_pos[0], curr_pos[1], self.polygon)
        was_inside = track_id in self.active_queue
        
        prev_pos = self.last_coordinates.get(track_id)
        self.last_coordinates[track_id] = curr_pos

        if is_inside and not was_inside:
            # Join queue
            self.active_queue[track_id] = timestamp
            events.append({
                "store_id": self.store_id,
                "camera_id": "CAM5",
                "local_tracker_id": track_id,
                "event_type": "BILLING_QUEUE_JOIN",
                "zone_id": "billing_queue",
                "timestamp": timestamp,
                "dwell_time_seconds": None,
                "bounding_box": [0, 0, 0, 0],
                "detection_confidence": 0.95
            })
            
            # Check for queue depth spike
            current_depth = len(self.active_queue)
            if current_depth > self.spike_threshold and not self.spike_alert_active:
                self.spike_alert_active = True
                print(f"!!! QUEUE SPIKE ALERT !!! Depth is now {current_depth} people.")
                # In production, this can trigger a Slack alert, PagerDuty, or manager notification

        elif not is_inside and was_inside:
            # Exit queue
            entry_time_str = self.active_queue.pop(track_id)
            
            # Reset spike alert state if queue depth drops below threshold
            if len(self.active_queue) <= self.spike_threshold:
                self.spike_alert_active = False
                
            # Calculate dwell time
            try:
                t_entry = datetime.datetime.fromisoformat(entry_time_str.replace("Z", "+00:00"))
                t_exit = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                dwell_time = (t_exit - t_entry).total_seconds()
            except Exception:
                dwell_time = 0.0

            # Determine exit direction:
            # If y coordinate is decreasing (moving UP-screen, e.g. back towards skincare/makeup zone)
            # instead of exiting down-screen (checkout registers), it is a queue abandonment!
            is_abandonment = False
            if prev_pos:
                dy = curr_pos[1] - prev_pos[1]
                if dy < 0:  # Moving up the screen (away from checkout registers)
                    is_abandonment = True

            event_type = "BILLING_QUEUE_ABANDON" if is_abandonment else "ZONE_EXIT"
            
            events.append({
                "store_id": self.store_id,
                "camera_id": "CAM5",
                "local_tracker_id": track_id,
                "event_type": event_type,
                "zone_id": "billing_queue",
                "timestamp": timestamp,
                "dwell_time_seconds": round(dwell_time, 2),
                "bounding_box": [0, 0, 0, 0],
                "detection_confidence": 0.95
            })
            
        return events

    def get_queue_depth(self) -> int:
        return len(self.active_queue)


# --- Unit Tests ---

class TestQueueTracking(unittest.TestCase):
    def setUp(self):
        # 100x100 rectangular polygon zone representing billing queue
        self.polygon = [(100, 100), (200, 100), (200, 200), (100, 200)]
        self.analyzer = QueueAnalyzer(self.polygon, spike_threshold=2)

    def test_queue_join(self):
        """
        Verify entering the queue triggers BILLING_QUEUE_JOIN.
        """
        events = self.analyzer.update_track(1, (150, 150), "2026-06-02T10:00:00.000Z")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "BILLING_QUEUE_JOIN")
        self.assertEqual(self.analyzer.get_queue_depth(), 1)

    def test_queue_spike(self):
        """
        Verify that exceeding the depth threshold triggers spike alert tracking.
        """
        # Spike threshold is set to 2. Let's add 3 people.
        self.analyzer.update_track(1, (150, 150), "2026-06-02T10:00:00.000Z")
        self.analyzer.update_track(2, (160, 160), "2026-06-02T10:00:01.000Z")
        
        # 3rd person joins -> triggers spike state
        self.analyzer.update_track(3, (170, 170), "2026-06-02T10:00:02.000Z")
        self.assertTrue(self.analyzer.spike_alert_active)
        self.assertEqual(self.analyzer.get_queue_depth(), 3)

    def test_queue_abandon(self):
        """
        Verify that exiting the queue in the upward direction (decreasing Y) triggers BILLING_QUEUE_ABANDON.
        """
        # Enter queue
        self.analyzer.update_track(4, (150, 150), "2026-06-02T10:00:00.000Z")
        
        # Move up inside queue first to set last coordinate
        self.analyzer.update_track(4, (150, 140), "2026-06-02T10:00:05.000Z")
        
        # Exit queue going up (y decreases to 90, which is outside the y=100-200 polygon)
        events = self.analyzer.update_track(4, (150, 90), "2026-06-02T10:00:10.000Z")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "BILLING_QUEUE_ABANDON")
        self.assertEqual(events[0]["dwell_time_seconds"], 10.0)

    def test_queue_normal_exit(self):
        """
        Verify that exiting downward (increasing Y) triggers normal exit (checkout).
        """
        # Enter queue
        self.analyzer.update_track(5, (150, 150), "2026-06-02T10:00:00.000Z")
        
        # Move down inside queue
        self.analyzer.update_track(5, (150, 180), "2026-06-02T10:00:05.000Z")
        
        # Exit queue going down (y increases to 220, which is outside the y=100-200 polygon)
        events = self.analyzer.update_track(5, (150, 220), "2026-06-02T10:00:10.000Z")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "ZONE_EXIT")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.argv.pop(1)
        unittest.main()
    else:
        # Example standalone run: Simulating queue join, spike alert, and abandonment
        # billing_queue_poly mapped to 4K resolution
        billing_queue_poly = [(1200, 1200), (3000, 1200), (3000, 2800), (1200, 2800)]
        analyzer = QueueAnalyzer(billing_queue_poly, spike_threshold=2)
        
        print("Simulating billing queue tracking events...")
        t0 = "2026-06-02T15:00:00.000Z"
        t1 = "2026-06-02T15:00:05.000Z"
        t2 = "2026-06-02T15:00:10.000Z"
        t3 = "2026-06-02T15:00:15.000Z"
        
        # Visitor 1 joins
        print("\n--- Visitor 1 joins queue ---")
        evs = analyzer.update_track(1, (1500, 1500), t0)
        
        # Visitor 2 joins
        print("--- Visitor 2 joins queue ---")
        evs = analyzer.update_track(2, (1600, 1600), t1)
        
        # Visitor 3 joins -> triggers spike warning
        print("--- Visitor 3 joins queue (Spike Trigger) ---")
        evs = analyzer.update_track(3, (1700, 1700), t2)
        
        # Visitor 1 exits downward (checkout complete)
        print("--- Visitor 1 exits downward (checkout completed) ---")
        analyzer.update_track(1, (1500, 1600), t1) # set last coordinate
        evs = analyzer.update_track(1, (1500, 3000), t3)
        for e in evs:
            print(f"Triggered: {e['event_type']} | Dwell Time: {e['dwell_time_seconds']}s")
            
        # Visitor 2 exits upward (abandonment)
        print("--- Visitor 2 exits upward (abandoned queue) ---")
        analyzer.update_track(2, (1600, 1500), t1) # set last coordinate
        evs = analyzer.update_track(2, (1600, 1000), t3)
        for e in evs:
            print(f"Triggered: {e['event_type']} | Dwell Time: {e['dwell_time_seconds']}s")
