from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, Any
import logging

logger = logging.getLogger("store_intelligence.services")

class MetricsService:
    """
    Service layer responsible for calculating live physical store retail analytics 
    from camera event logs and POS transaction databases.
    """
    def __init__(self, db: Session):
        self.db = db

    def calculate_unique_visitors(self, store_id: str) -> int:
        """
        Returns the count of total unique visitors detected inside the store (non-staff).
        """
        try:
            # We filter out sessions identified as staff if applicable, but default query on event visitor_ids
            query = text("""
                SELECT COUNT(DISTINCT visitor_id)
                FROM events
                WHERE store_id = :store_id AND visitor_id IS NOT NULL
            """)
            result = self.db.execute(query, {"store_id": store_id}).scalar()
            return result or 0
        except Exception as e:
            logger.error(f"Error calculating unique visitors for store {store_id}: {str(e)}", exc_info=True)
            return 0

    def calculate_conversion_rate(self, store_id: str) -> float:
        """
        Returns the offline conversion rate percentage (Converted Visitors / Total Unique Visitors).
        A visitor is considered converted if they have completed a POS checkout transaction.
        """
        try:
            total_visitors = self.calculate_unique_visitors(store_id)
            if total_visitors == 0:
                return 0.0

            converted_query = text("""
                SELECT COUNT(DISTINCT visitor_id)
                FROM transactions
                WHERE store_id = :store_id AND visitor_id IS NOT NULL
            """)
            converted_visitors = self.db.execute(converted_query, {"store_id": store_id}).scalar() or 0

            conversion_rate = (converted_visitors / total_visitors) * 100.0
            return round(conversion_rate, 2)
        except Exception as e:
            logger.error(f"Error calculating conversion rate for store {store_id}: {str(e)}", exc_info=True)
            return 0.0

    def calculate_avg_dwell_time(self, store_id: str) -> float:
        """
        Returns the average dwell time of store visitors in minutes.
        """
        try:
            query = text("""
                SELECT AVG(total_dwell_seconds)
                FROM sessions
                WHERE store_id = :store_id AND total_dwell_seconds IS NOT NULL
            """)
            avg_dwell_seconds = self.db.execute(query, {"store_id": store_id}).scalar()
            
            if avg_dwell_seconds is not None:
                return round(avg_dwell_seconds / 60.0, 2)
            
            # Fallback to exits in events log if sessions are not computed
            fallback_query = text("""
                SELECT AVG(dwell_time_seconds)
                FROM events
                WHERE store_id = :store_id AND event_type = 'EXIT' AND dwell_time_seconds IS NOT NULL
            """)
            avg_event_dwell = self.db.execute(fallback_query, {"store_id": store_id}).scalar()
            if avg_event_dwell is not None:
                return round(avg_event_dwell / 60.0, 2)
                
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating avg dwell time for store {store_id}: {str(e)}", exc_info=True)
            return 0.0

    def calculate_queue_depth(self, store_id: str) -> int:
        """
        Calculates the current real-time queue depth in the checkout lane (CAM5).
        Identifies active visitors in the queue who joined but have not yet exited/abandoned it.
        """
        try:
            query = text("""
                WITH latest_queue_events AS (
                    SELECT e1.visitor_id, e1.event_type, e1.timestamp
                    FROM events e1
                    INNER JOIN (
                        SELECT visitor_id, MAX(timestamp) as max_ts
                        FROM events
                        WHERE store_id = :store_id
                          AND camera_id = 'CAM5'
                          AND event_type IN ('BILLING_QUEUE_JOIN', 'BILLING_QUEUE_ABANDON', 'ZONE_EXIT')
                          AND visitor_id IS NOT NULL
                        GROUP BY visitor_id
                    ) e2 ON e1.visitor_id = e2.visitor_id AND e1.timestamp = e2.max_ts
                    WHERE e1.store_id = :store_id
                      AND e1.camera_id = 'CAM5'
                )
                SELECT COUNT(*) 
                FROM latest_queue_events 
                WHERE event_type = 'BILLING_QUEUE_JOIN'
            """)
            result = self.db.execute(query, {"store_id": store_id}).scalar()
            return result or 0
        except Exception as e:
            logger.error(f"Error calculating queue depth for store {store_id}: {str(e)}", exc_info=True)
            return 0

    def calculate_abandonment_rate(self, store_id: str) -> float:
        """
        Returns the queue abandonment rate percentage (Queue Abandonments / Total Queue Joins).
        """
        try:
            query_joins = text("""
                SELECT COUNT(*)
                FROM events
                WHERE store_id = :store_id 
                  AND camera_id = 'CAM5' 
                  AND event_type = 'BILLING_QUEUE_JOIN'
            """)
            joins = self.db.execute(query_joins, {"store_id": store_id}).scalar() or 0
            if joins == 0:
                return 0.0

            query_abandons = text("""
                SELECT COUNT(*)
                FROM events
                WHERE store_id = :store_id 
                  AND camera_id = 'CAM5' 
                  AND event_type = 'BILLING_QUEUE_ABANDON'
            """)
            abandons = self.db.execute(query_abandons, {"store_id": store_id}).scalar() or 0

            abandon_rate = (abandons / joins) * 100.0
            return round(abandon_rate, 2)
        except Exception as e:
            logger.error(f"Error calculating queue abandonment rate for store {store_id}: {str(e)}", exc_info=True)
            return 0.0

    def get_all_metrics(self, store_id: str) -> Dict[str, Any]:
        """
        Calculates and returns a comprehensive dictionary of all store retail performance metrics.
        """
        visitors = self.calculate_unique_visitors(store_id)
        
        try:
            converted_query = text("""
                SELECT COUNT(DISTINCT visitor_id)
                FROM transactions
                WHERE store_id = :store_id AND visitor_id IS NOT NULL
            """)
            buyers = self.db.execute(converted_query, {"store_id": store_id}).scalar() or 0
        except Exception as e:
            logger.error(f"Error calculating buyers for store {store_id}: {str(e)}", exc_info=True)
            buyers = 0
            
        conversion_rate = (buyers / visitors * 100.0) if visitors > 0 else 0.0

        return {
            "unique_visitors": visitors,
            "unique_buyers": buyers,
            "conversion_rate_percentage": round(conversion_rate, 2),
            "avg_dwell_time_minutes": self.calculate_avg_dwell_time(store_id),
            "current_queue_depth": self.calculate_queue_depth(store_id),
            "queue_abandonment_rate_percentage": self.calculate_abandonment_rate(store_id),
        }
