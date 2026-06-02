import os
import sys
import json
import csv
import datetime
import unittest
from typing import Dict, Tuple, Optional, List
import httpx

# API configuration
API_URL = "http://localhost:8000/events/ingest"
STORE_ID = "ST1008"

class DwellTracker:
    def __init__(self, store_id: str = "ST1008", dwell_interval_seconds: float = 30.0):
        self.store_id = store_id
        self.dwell_interval_ms = dwell_interval_seconds * 1000.0
        
        # State tracking: track_id -> dict
        # Structure: {
        #   "zone_id": str,
        #   "enter_time": datetime,
        #   "last_trigger_time": datetime,
        #   "total_dwell_ms": float
        # }
        self.active_dwells: Dict[int, Dict] = {}
        
        # Dwell history: track_id -> List of historical completed visits: (zone_id, dwell_ms)
        self.dwell_history: Dict[int, List[Tuple[str, float]]] = {}

    def parse_timestamp(self, ts_str: str) -> datetime.datetime:
        """
        Parses ISO format timestamps into timezone-aware datetime objects.
        """
        return datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))

    def update_track(self, track_id: int, is_inside: bool, zone_id: str, timestamp_str: str) -> Optional[Dict]:
        """
        Updates a track state with its current zone containment.
        Returns a ZONE_DWELL event dictionary if a 30-second interval has passed, else None.
        """
        curr_time = self.parse_timestamp(timestamp_str)
        
        if is_inside:
            if track_id not in self.active_dwells:
                # ZONE_ENTER (Start Dwell Tracking)
                self.active_dwells[track_id] = {
                    "zone_id": zone_id,
                    "enter_time": curr_time,
                    "last_trigger_time": curr_time,
                    "total_dwell_ms": 0.0
                }
                return None
            
            dwell_state = self.active_dwells[track_id]
            
            # If the visitor switched zones, close the previous dwell and open a new one
            if dwell_state["zone_id"] != zone_id:
                self.close_dwell(track_id, curr_time)
                self.active_dwells[track_id] = {
                    "zone_id": zone_id,
                    "enter_time": curr_time,
                    "last_trigger_time": curr_time,
                    "total_dwell_ms": 0.0
                }
                return None
                
            # Calculate cumulative dwell in milliseconds
            elapsed_ms = (curr_time - dwell_state["enter_time"]).total_seconds() * 1000.0
            dwell_state["total_dwell_ms"] = elapsed_ms
            
            # Check if 30 seconds has elapsed since the last trigger
            ms_since_last_trigger = (curr_time - dwell_state["last_trigger_time"]).total_seconds() * 1000.0
            
            if ms_since_last_trigger >= self.dwell_interval_ms:
                # Trigger ZONE_DWELL event
                dwell_state["last_trigger_time"] = curr_time
                
                event = {
                    "store_id": self.store_id,
                    "camera_id": "CAM1" if zone_id == "skincare" else ("CAM2" if zone_id == "makeup" else "CAM5"),
                    "local_tracker_id": track_id,
                    "event_type": "ZONE_DWELL",
                    "zone_id": zone_id,
                    "timestamp": timestamp_str,
                    "dwell_time_seconds": round(elapsed_ms / 1000.0, 2),
                    "bounding_box": [0, 0, 0, 0], # Bounding box placeholder
                    "detection_confidence": 0.95
                }
                # Attach extra raw metadata for tracking verification
                event["metadata"] = {
                    "dwell_ms": round(elapsed_ms, 1)
                }
                return event
                
        else:
            # If they were inside, but are now outside, close the active session
            if track_id in self.active_dwells:
                self.close_dwell(track_id, curr_time)
                
        return None

    def close_dwell(self, track_id: int, exit_time: datetime.datetime):
        """
        Closes active dwell session and saves stats into history logs.
        """
        dwell_state = self.active_dwells.pop(track_id)
        zone_id = dwell_state["zone_id"]
        total_ms = (exit_time - dwell_state["enter_time"]).total_seconds() * 1000.0
        
        if track_id not in self.dwell_history:
            self.dwell_history[track_id] = []
        self.dwell_history[track_id].append((zone_id, total_ms))
        
        print(f"Closed Dwell Session for Visitor {track_id} in {zone_id} | Total Dwell: {total_ms:.1f}ms")


# --- Unit Tests ---

class TestDwellTracking(unittest.TestCase):
    def setUp(self):
        # Initialize with a 30s interval
        self.tracker = DwellTracker(dwell_interval_seconds=30.0)
        
    def test_dwell_initialization(self):
        """
        Check that entering a zone starts tracking but does not trigger DWELL instantly.
        """
        res = self.tracker.update_track(1, True, "skincare", "2026-06-02T10:00:00.000Z")
        self.assertIsNone(res)
        self.assertIn(1, self.tracker.active_dwells)
        self.assertEqual(self.tracker.active_dwells[1]["zone_id"], "skincare")

    def test_periodic_dwell_trigger(self):
        """
        Verify that a ZONE_DWELL event is triggered exactly after 30 seconds.
        """
        # Enter at 10:00:00
        self.tracker.update_track(2, True, "skincare", "2026-06-02T10:00:00.000Z")
        
        # 15 seconds elapsed -> should not trigger
        res = self.tracker.update_track(2, True, "skincare", "2026-06-02T10:00:15.000Z")
        self.assertIsNone(res)
        
        # 30 seconds elapsed -> triggers ZONE_DWELL with 30s dwell_time_seconds
        res = self.tracker.update_track(2, True, "skincare", "2026-06-02T10:00:30.000Z")
        self.assertIsNotNone(res)
        self.assertEqual(res["event_type"], "ZONE_DWELL")
        self.assertEqual(res["dwell_time_seconds"], 30.0)
        self.assertEqual(res["metadata"]["dwell_ms"], 30000.0)
        
        # 45 seconds elapsed -> should not trigger
        res = self.tracker.update_track(2, True, "skincare", "2026-06-02T10:00:45.000Z")
        self.assertIsNone(res)

        # 60 seconds elapsed (30s since last trigger) -> triggers second ZONE_DWELL
        res = self.tracker.update_track(2, True, "skincare", "2026-06-02T10:01:00.000Z")
        self.assertIsNotNone(res)
        self.assertEqual(res["dwell_time_seconds"], 60.0)
        self.assertEqual(res["metadata"]["dwell_ms"], 60000.0)

    def test_zone_switch(self):
        """
        Verify that switching zones resets the timers correctly.
        """
        self.tracker.update_track(3, True, "skincare", "2026-06-02T10:00:00.000Z")
        
        # Switch to makeup zone at 10:00:10 -> closes skincare, starts makeup
        self.tracker.update_track(3, True, "makeup", "2026-06-02T10:00:10.000Z")
        self.assertIn(3, self.tracker.dwell_history) # Skincare dwell closed (saved to history)
        self.assertEqual(self.tracker.active_dwells[3]["zone_id"], "makeup")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        sys.argv.pop(1)
        unittest.main()
    else:
        # Example standalone execution: Simulating 70 seconds of track dwell inside skincare zone
        tracker = DwellTracker(store_id=STORE_ID, dwell_interval_seconds=30.0)
        
        print("Simulating a visitor entering skincare and standing for 70 seconds...")
        
        t0 = "2026-06-02T12:00:00.000Z"
        t1 = "2026-06-02T12:00:15.000Z"
        t2 = "2026-06-02T12:00:30.000Z" # 30s trigger mark
        t3 = "2026-06-02T12:00:45.000Z"
        t4 = "2026-06-02T12:01:00.000Z" # 60s trigger mark
        t5 = "2026-06-02T12:01:10.000Z" # Exit at 70s
        
        # Enter
        tracker.update_track(101, True, "skincare", t0)
        # Updates
        tracker.update_track(101, True, "skincare", t1)
        
        # Check 30s
        ev1 = tracker.update_track(101, True, "skincare", t2)
        if ev1:
            print(f"Generated Event: {ev1['event_type']} | Dwell Time: {ev1['dwell_time_seconds']}s ({ev1['metadata']['dwell_ms']}ms)")
            
        tracker.update_track(101, True, "skincare", t3)
        
        # Check 60s
        ev2 = tracker.update_track(101, True, "skincare", t4)
        if ev2:
            print(f"Generated Event: {ev2['event_type']} | Dwell Time: {ev2['dwell_time_seconds']}s ({ev2['metadata']['dwell_ms']}ms)")
            
        # Exit
        tracker.update_track(101, False, "skincare", t5)
