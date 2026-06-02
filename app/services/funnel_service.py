from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("store_intelligence.services")

class FunnelService:
    """
    Service layer responsible for calculating session-based visitor conversion funnel analytics.
    Reconstructs visitor sessions dynamically from raw visual events and maps them to POS checkout transactions.
    """
    def __init__(self, db: Session):
        self.db = db

    def calculate_funnel(self, store_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Computes the dynamic funnel stage metrics.
        Stages:
          1. Entry
          2. Zone Visit
          3. Billing Queue Join
          4. Purchase Complete
        
        Handles:
          - Re-entry: Visitor entering the store multiple times within a day starts a new session if they exited
            or if there is an inactivity gap of > 30 minutes.
          - Session-based grouping: Raw detections grouped into logical visits.
          - Drop-off and step conversion calculations.
        """
        try:
            # 1. Fetch raw events sorted by visitor and timestamp
            query_events = """
                SELECT visitor_id, event_type, zone_id, camera_id, timestamp
                FROM events
                WHERE store_id = :store_id AND visitor_id IS NOT NULL
            """
            params = {"store_id": store_id}
            if start_time:
                query_events += " AND timestamp >= :start_time"
                params["start_time"] = start_time
            if end_time:
                query_events += " AND timestamp <= :end_time"
                params["end_time"] = end_time
                
            query_events += " ORDER BY visitor_id, timestamp ASC"
            
            events_rows = self.db.execute(text(query_events), params).fetchall()
            
            if not events_rows:
                return {
                    "store_id": store_id,
                    "data_source": "production_database",
                    "total_sessions": 0,
                    "stages": [
                        {"stage": "1_Entry", "count": 0, "conversion_from_previous_percentage": 0.0},
                        {"stage": "2_Zone_Interaction", "count": 0, "conversion_from_previous_percentage": 0.0},
                        {"stage": "3_Billing_Queue_Join", "count": 0, "conversion_from_previous_percentage": 0.0},
                        {"stage": "4_Purchase_Complete", "count": 0, "conversion_from_previous_percentage": 0.0}
                    ]
                }
            
            # 2. Fetch all transactions for association
            query_tx = """
                SELECT visitor_id, timestamp, amount
                FROM transactions
                WHERE store_id = :store_id AND visitor_id IS NOT NULL
            """
            tx_params = {"store_id": store_id}
            if start_time:
                query_tx += " AND timestamp >= :start_time"
                tx_params["start_time"] = start_time
            if end_time:
                query_tx += " AND timestamp <= :end_time"
                tx_params["end_time"] = end_time
                
            tx_rows = self.db.execute(text(query_tx), tx_params).fetchall()
            
            # Map transactions to visitor ID
            visitor_txs = {}
            for r in tx_rows:
                v_id = str(r[0])
                tx_time = r[1]
                if isinstance(tx_time, str):
                    try:
                        tx_time = datetime.fromisoformat(tx_time.replace("Z", "+00:00"))
                    except Exception:
                        pass
                visitor_txs.setdefault(v_id, []).append(tx_time)

            # 3. Group events by visitor_id
            visitor_events = {}
            for r in events_rows:
                v_id = str(r[0])
                ev_type = r[1]
                zone_id = r[2]
                camera_id = r[3]
                ev_time = r[4]
                
                if isinstance(ev_time, str):
                    try:
                        ev_time = datetime.fromisoformat(ev_time.replace("Z", "+00:00"))
                    except Exception:
                        pass
                        
                visitor_events.setdefault(v_id, []).append({
                    "event_type": ev_type,
                    "zone_id": zone_id,
                    "camera_id": camera_id,
                    "timestamp": ev_time
                })

            # 4. Reconstruct sessions with re-entry handling
            reconstructed_sessions = []
            session_timeout = timedelta(minutes=30)
            
            for v_id, evs in visitor_events.items():
                current_sess_events = []
                for ev in evs:
                    if not current_sess_events:
                        current_sess_events.append(ev)
                    else:
                        prev_ev = current_sess_events[-1]
                        time_gap = ev["timestamp"] - prev_ev["timestamp"]
                        
                        # End current session and begin new one if:
                        # - Previous event was EXIT
                        # - Time gap exceeds the timeout window (inactivity)
                        if prev_ev["event_type"] == "EXIT" or time_gap > session_timeout:
                            reconstructed_sessions.append((v_id, current_sess_events))
                            current_sess_events = [ev]
                        else:
                            current_sess_events.append(ev)
                if current_sess_events:
                    reconstructed_sessions.append((v_id, current_sess_events))

            # 5. Check stage progression for each session
            entry_count = 0
            zone_count = 0
            queue_count = 0
            purchase_count = 0
            
            for v_id, sess_evs in reconstructed_sessions:
                s_start = sess_evs[0]["timestamp"]
                s_end = sess_evs[-1]["timestamp"]
                
                # Stage 1: ENTRY is always met since we reconstructed a session from tracking events
                has_entry = True
                
                # Stage 2: ZONE VISIT
                has_zone = any(
                    ev["camera_id"] in ("CAM1", "CAM2") or 
                    ev["zone_id"] in ("skincare", "makeup") or
                    ev["event_type"] in ("ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL")
                    for ev in sess_evs
                )
                
                # Stage 3: BILLING QUEUE JOIN
                has_queue = any(
                    ev["camera_id"] == "CAM5" or 
                    ev["zone_id"] == "billing_queue" or
                    ev["event_type"] == "BILLING_QUEUE_JOIN"
                    for ev in sess_evs
                )
                
                # Stage 4: PURCHASE COMPLETE
                has_purchase = False
                txs = visitor_txs.get(v_id, [])
                for tx_time in txs:
                    # Transaction falls within session duration (with small checkout leeway of 30 mins)
                    if s_start - timedelta(minutes=5) <= tx_time <= s_end + timedelta(minutes=30):
                        has_purchase = True
                        break

                # Apply sequential funnel progression integrity
                if has_entry:
                    entry_count += 1
                    if has_zone:
                        zone_count += 1
                        if has_queue:
                            queue_count += 1
                            if has_purchase:
                                purchase_count += 1

            # 6. Calculate conversion and drop-off percentages
            conv_1 = 100.0
            conv_2 = round((zone_count / entry_count) * 100.0, 2) if entry_count > 0 else 0.0
            conv_3 = round((queue_count / zone_count) * 100.0, 2) if zone_count > 0 else 0.0
            conv_4 = round((purchase_count / queue_count) * 100.0, 2) if queue_count > 0 else 0.0

            return {
                "store_id": store_id,
                "data_source": "production_database",
                "total_sessions": len(reconstructed_sessions),
                "stages": [
                    {"stage": "1_Entry", "count": entry_count, "conversion_from_previous_percentage": conv_1},
                    {"stage": "2_Zone_Interaction", "count": zone_count, "conversion_from_previous_percentage": conv_2},
                    {"stage": "3_Billing_Queue_Join", "count": queue_count, "conversion_from_previous_percentage": conv_3},
                    {"stage": "4_Purchase_Complete", "count": purchase_count, "conversion_from_previous_percentage": conv_4}
                ]
            }

        except Exception as e:
            logger.error(f"Error calculating funnel for store {store_id}: {str(e)}", exc_info=True)
            raise e
