import datetime
from sqlalchemy import text
from app.db.session import SessionLocal

def associate():
    print("=" * 60)
    print("RUNNING TEMPORAL TRANSACTION-VISITOR ASSOCIATION")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # Find all checkout events (BILLING_QUEUE_JOIN at CAM5)
        checkout_events = db.execute(
            text("""
                SELECT id, visitor_id, timestamp
                FROM events
                WHERE camera_id = 'CAM5'
                  AND event_type = 'BILLING_QUEUE_JOIN'
                  AND visitor_id IS NOT NULL
            """)
        ).fetchall()
        
        if not checkout_events:
            print("No visual checkout events found in database. Run the edge pipeline first!")
            return

        print(f"Found {len(checkout_events)} visual checkout events. Mapping to POS transactions...")
        
        linked_count = 0
        for event in checkout_events:
            event_id, visitor_id, event_time = event
            
            # Find the closest transaction in time (in the same store)
            closest_tx = db.execute(
                text("""
                    SELECT id, pos_transaction_id, timestamp, amount
                    FROM transactions
                    WHERE visitor_id IS NULL
                    ORDER BY ABS(EXTRACT(EPOCH FROM (timestamp - :event_time))) ASC
                    LIMIT 1
                """),
                {"event_time": event_time}
            ).fetchone()
            
            if closest_tx:
                tx_id, pos_id, tx_time, amount = closest_tx
                time_diff = abs((tx_time - event_time).total_seconds())
                
                # Link transaction to resolved visitor
                db.execute(
                    text("UPDATE transactions SET visitor_id = :visitor_id WHERE id = :tx_id"),
                    {"visitor_id": visitor_id, "tx_id": tx_id}
                )
                print(f"Linked POS {pos_id} (${amount}) to Visitor {visitor_id} (Time diff: {time_diff:.1f}s)")
                linked_count += 1
            else:
                print(f"No free POS transaction found to associate with Visitor {visitor_id}")

        db.commit()
        print("-" * 60)
        print(f"Association complete! Successfully linked {linked_count} transactions.")
        print("=" * 60)
        
    except Exception as e:
        db.rollback()
        print(f"Transaction association failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    associate()
