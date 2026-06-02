import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from app.db.base import Base
from app.models.database import Store, Camera, Visitor, Event, Transaction
from app.services.funnel_service import FunnelService
import uuid

@pytest.fixture
def db_session():
    # Set up a clean, isolated, in-memory SQLite database for test execution
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Seed mock store and camera records
    session.execute(text("""
        INSERT INTO stores (id, name, address, timezone)
        VALUES ('ST1008', 'Test Store', 'Test Address', 'UTC')
    """))
    session.execute(text("""
        INSERT INTO cameras (id, store_id, name, camera_type)
        VALUES 
            ('CAM3', 'ST1008', 'Entry Camera', 'ENTRY_EXIT'),
            ('CAM1', 'ST1008', 'Skincare Camera', 'ZONE'),
            ('CAM2', 'ST1008', 'Makeup Camera', 'ZONE'),
            ('CAM5', 'ST1008', 'Billing Camera', 'BILLING')
    """))
    session.commit()
    
    yield session
    session.close()

def test_funnel_reentry_handling(db_session):
    # Test that visitor re-entry is parsed into multiple distinct sessions.
    visitor_id = str(uuid.uuid4())
    base_time = datetime(2026, 6, 2, 10, 0, 0)
    
    # Register visitor profile
    db_session.execute(text("""
        INSERT INTO visitors (id, store_id, first_seen, last_seen)
        VALUES (:id, 'ST1008', :t, :t)
    """), {"id": visitor_id, "t": base_time})
    
    # Session 1: Entry, Zone Visit, Exit
    db_session.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', NULL, :t1, 0.95),
            (:e2, 'ST1008', 'CAM1', :v, 'ZONE_ENTER', 'skincare', :t2, 0.92),
            (:e3, 'ST1008', 'CAM3', :v, 'EXIT', NULL, :t3, 0.94)
    """), {
        "v": visitor_id,
        "e1": str(uuid.uuid4()), "t1": base_time,
        "e2": str(uuid.uuid4()), "t2": base_time + timedelta(minutes=2),
        "e3": str(uuid.uuid4()), "t3": base_time + timedelta(minutes=10)
    })
    
    # Session 2 (Re-entry after 2 hours): Entry, Zone Visit (Makeup), Queue Join, Exit
    reentry_time = base_time + timedelta(hours=2)
    db_session.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', NULL, :t1, 0.95),
            (:e2, 'ST1008', 'CAM2', :v, 'ZONE_ENTER', 'makeup', :t2, 0.92),
            (:e3, 'ST1008', 'CAM5', :v, 'BILLING_QUEUE_JOIN', 'billing_queue', :t3, 0.94)
    """), {
        "v": visitor_id,
        "e1": str(uuid.uuid4()), "t1": reentry_time,
        "e2": str(uuid.uuid4()), "t2": reentry_time + timedelta(minutes=5),
        "e3": str(uuid.uuid4()), "t3": reentry_time + timedelta(minutes=8)
    })
    
    db_session.commit()
    
    # Initialize service and compute funnel
    service = FunnelService(db_session)
    result = service.calculate_funnel("ST1008")
    
    # Verify both sessions were reconstructed
    assert result["total_sessions"] == 2
    
    # Verify stages
    # Stage 1: Entry count should be 2 (both sessions counted)
    # Stage 2: Zone interaction count should be 2 (both visited a zone)
    # Stage 3: Billing queue count should be 1 (only session 2 joined queue)
    # Stage 4: Purchase count should be 0 (no transaction seeded yet)
    stages = {s["stage"]: s for s in result["stages"]}
    
    assert stages["1_Entry"]["count"] == 2
    assert stages["2_Zone_Interaction"]["count"] == 2
    assert stages["3_Billing_Queue_Join"]["count"] == 1
    assert stages["4_Purchase_Complete"]["count"] == 0

def test_funnel_stage_conversions(db_session):
    # Setup 4 distinct visitors, representing each stage of the funnel:
    # Visitor A: Reaches PURCHASE (Entry -> Zone -> Queue -> Purchase)
    # Visitor B: Reaches BILLING QUEUE (Entry -> Zone -> Queue, No Purchase)
    # Visitor C: Reaches ZONE Interaction (Entry -> Zone, No Queue)
    # Visitor D: Reaches ENTRY only (Entry, No Zone)
    
    v_a = str(uuid.uuid4())
    v_b = str(uuid.uuid4())
    v_c = str(uuid.uuid4())
    v_d = str(uuid.uuid4())
    
    base_time = datetime(2026, 6, 2, 12, 0, 0)
    
    # Insert visitor profiles
    for idx, vid in enumerate([v_a, v_b, v_c, v_d]):
        db_session.execute(text("""
            INSERT INTO visitors (id, store_id, first_seen, last_seen)
            VALUES (:id, 'ST1008', :t, :t)
        """), {"id": vid, "t": base_time})
        
    # Seed events for Visitor A (Full conversion)
    db_session.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', NULL, :t1, 0.95),
            (:e2, 'ST1008', 'CAM1', :v, 'ZONE_ENTER', 'skincare', :t2, 0.92),
            (:e3, 'ST1008', 'CAM5', :v, 'BILLING_QUEUE_JOIN', 'billing_queue', :t3, 0.93)
    """), {
        "v": v_a,
        "e1": str(uuid.uuid4()), "t1": base_time,
        "e2": str(uuid.uuid4()), "t2": base_time + timedelta(minutes=1),
        "e3": str(uuid.uuid4()), "t3": base_time + timedelta(minutes=5)
    })
    
    # Associate checkout transaction for Visitor A
    db_session.execute(text("""
        INSERT INTO transactions (id, store_id, visitor_id, pos_transaction_id, amount, timestamp)
        VALUES (:tx_id, 'ST1008', :v, 'POS-9999', 49.99, :tx_time)
    """), {
        "tx_id": str(uuid.uuid4()),
        "v": v_a,
        "tx_time": base_time + timedelta(minutes=10)
    })
    
    # Seed events for Visitor B (Abandons queue)
    db_session.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', NULL, :t1, 0.95),
            (:e2, 'ST1008', 'CAM2', :v, 'ZONE_ENTER', 'makeup', :t2, 0.92),
            (:e3, 'ST1008', 'CAM5', :v, 'BILLING_QUEUE_JOIN', 'billing_queue', :t3, 0.93),
            (:e4, 'ST1008', 'CAM5', :v, 'BILLING_QUEUE_ABANDON', 'billing_queue', :t4, 0.91)
    """), {
        "v": v_b,
        "e1": str(uuid.uuid4()), "t1": base_time,
        "e2": str(uuid.uuid4()), "t2": base_time + timedelta(minutes=2),
        "e3": str(uuid.uuid4()), "t3": base_time + timedelta(minutes=7),
        "e4": str(uuid.uuid4()), "t4": base_time + timedelta(minutes=15)
    })
    
    # Seed events for Visitor C (Leaves after browsing zone)
    db_session.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', NULL, :t1, 0.95),
            (:e2, 'ST1008', 'CAM2', :v, 'ZONE_ENTER', 'makeup', :t2, 0.92),
            (:e3, 'ST1008', 'CAM2', :v, 'ZONE_EXIT', 'makeup', :t3, 0.92)
    """), {
        "v": v_c,
        "e1": str(uuid.uuid4()), "t1": base_time,
        "e2": str(uuid.uuid4()), "t2": base_time + timedelta(minutes=3),
        "e3": str(uuid.uuid4()), "t3": base_time + timedelta(minutes=6)
    })
    
    # Seed events for Visitor D (Enters and leaves directly)
    db_session.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', NULL, :t1, 0.95),
            (:e2, 'ST1008', 'CAM3', :v, 'EXIT', NULL, :t2, 0.95)
    """), {
        "v": v_d,
        "e1": str(uuid.uuid4()), "t1": base_time,
        "e2": str(uuid.uuid4()), "t2": base_time + timedelta(minutes=4)
    })
    
    db_session.commit()
    
    service = FunnelService(db_session)
    result = service.calculate_funnel("ST1008")
    
    assert result["total_sessions"] == 4
    
    stages = {s["stage"]: s for s in result["stages"]}
    
    # Entry count: A, B, C, D (4)
    assert stages["1_Entry"]["count"] == 4
    # Zone Interaction count: A, B, C (3)
    assert stages["2_Zone_Interaction"]["count"] == 3
    # Billing Queue Join count: A, B (2)
    assert stages["3_Billing_Queue_Join"]["count"] == 2
    # Purchase count: A (1)
    assert stages["4_Purchase_Complete"]["count"] == 1
    
    # Check conversion percentages
    assert stages["1_Entry"]["conversion_from_previous_percentage"] == 100.0
    assert stages["2_Zone_Interaction"]["conversion_from_previous_percentage"] == 75.0  # 3/4
    assert stages["3_Billing_Queue_Join"]["conversion_from_previous_percentage"] == 66.67  # 2/3
    assert stages["4_Purchase_Complete"]["conversion_from_previous_percentage"] == 50.0  # 1/2
