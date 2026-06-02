import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone, timedelta
import uuid
import json

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.services.funnel_service import FunnelService
from app.services.metrics_service import MetricsService

# Setup in-memory SQLite database for test runs
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    # Create tables and clean setup
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    
    # Seed default store and camera records
    db_session.execute(text("""
        INSERT INTO stores (id, name, address, timezone)
        VALUES ('ST1008', 'Brigade Road Store', 'Brigade Road, Bangalore', 'UTC')
    """))
    db_session.execute(text("""
        INSERT INTO cameras (id, store_id, name, camera_type)
        VALUES 
            ('CAM3', 'ST1008', 'Entry Camera', 'ENTRY_EXIT'),
            ('CAM1', 'ST1008', 'Skincare Camera', 'ZONE'),
            ('CAM2', 'ST1008', 'Makeup Camera', 'ZONE'),
            ('CAM5', 'ST1008', 'Billing Camera', 'BILLING')
    """))
    db_session.commit()
    
    yield db_session
    
    db_session.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    # Override get_db dependency for FastAPI
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ==============================================================================
# 1. Test Entry Detection & Ingestion
# ==============================================================================
def test_entry_detection(client, db):
    payload = {
        "store_id": "ST1008",
        "camera_id": "CAM3",
        "local_tracker_id": 100,
        "event_type": "ENTRY",
        "zone_id": None,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "bounding_box": [320.0, 400.0, 380.0, 480.0],
        "detection_confidence": 0.95,
        "visual_embedding": [0.1] * 512
    }
    
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 201
    res_json = response.json()
    assert res_json["status"] == "success"
    assert "resolved_visitor_id" in res_json
    
    # Query DB to check if entry event was recorded
    visitor_id = res_json["resolved_visitor_id"]
    event = db.execute(text("SELECT event_type, camera_id FROM events WHERE visitor_id = :v"), {"v": visitor_id}).fetchone()
    assert event is not None
    assert event[0] == "ENTRY"
    assert event[1] == "CAM3"


# ==============================================================================
# 2. Test Exit Detection
# ==============================================================================
def test_exit_detection(client, db):
    visitor_id = str(uuid.uuid4())
    # Create visitor profile
    db.execute(text("""
        INSERT INTO visitors (id, store_id, first_seen, last_seen)
        VALUES (:id, 'ST1008', :t, :t)
    """), {"id": visitor_id, "t": datetime.now(timezone.utc)})
    
    payload = {
        "store_id": "ST1008",
        "camera_id": "CAM3",
        "local_tracker_id": 100,
        "event_type": "EXIT",
        "zone_id": None,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "dwell_time_seconds": 350.5,
        "bounding_box": [320.0, 400.0, 380.0, 480.0],
        "detection_confidence": 0.95,
        "visual_embedding": [0.1] * 512  # Re-ID matching will target this visitor
    }
    
    response = client.post("/events/ingest", json=payload)
    assert response.status_code == 201
    
    # Verify the event is recorded as EXIT with the correct dwell time
    event = db.execute(text("SELECT event_type, dwell_time_seconds FROM events WHERE visitor_id = :v"), {"v": visitor_id}).fetchone()
    assert event is not None
    assert event[0] == "EXIT"
    assert event[1] == 350.5


# ==============================================================================
# 3. Test Visitor Re-Entry Handling
# ==============================================================================
def test_visitor_reentry(db):
    visitor_id = str(uuid.uuid4())
    base_time = datetime(2026, 6, 2, 10, 0, 0, tzinfo=timezone.utc)
    
    # Insert visitor
    db.execute(text("""
        INSERT INTO visitors (id, store_id, first_seen, last_seen)
        VALUES (:id, 'ST1008', :t, :t)
    """), {"id": visitor_id, "t": base_time})
    
    # Session 1 events (Entry -> Exit)
    db.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', :t1, 0.95),
            (:e2, 'ST1008', 'CAM3', :v, 'EXIT', :t2, 0.95)
    """), {
        "v": visitor_id,
        "e1": str(uuid.uuid4()), "t1": base_time,
        "e2": str(uuid.uuid4()), "t2": base_time + timedelta(minutes=10)
    })
    
    # Session 2 events (Re-entry 1 hour later)
    reentry_time = base_time + timedelta(hours=1)
    db.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', :t1, 0.95)
    """), {
        "v": visitor_id,
        "e1": str(uuid.uuid4()), "t1": reentry_time
    })
    db.commit()
    
    funnel_service = FunnelService(db)
    funnel = funnel_service.calculate_funnel("ST1008")
    
    # Re-entry: should identify 2 distinct visit sessions
    assert funnel["total_sessions"] == 2


# ==============================================================================
# 4. Test Empty Store Handling
# ==============================================================================
def test_empty_store(client, db):
    # Ensure database tables are completely empty of events
    db.execute(text("DELETE FROM events"))
    db.execute(text("DELETE FROM visitors"))
    db.execute(text("DELETE FROM transactions"))
    db.commit()
    
    # Metrics Endpoint: should return default/mock fallback metrics or zeros gracefully
    metrics_response = client.get("/stores/ST1008/metrics")
    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    assert "metrics" in metrics
    
    # Funnel Endpoint: should trigger fallback dataset
    funnel_response = client.get("/stores/ST1008/funnel")
    assert funnel_response.status_code == 200
    funnel = funnel_response.json()
    assert len(funnel["stages"]) == 4
    # The count should contain baseline values from the mock_fallback
    assert funnel["data_source"] == "mock_fallback"


# ==============================================================================
# 5. Test Queue Spike Detection (Anomalies)
# ==============================================================================
def test_queue_spike_detection(client, db):
    # Seed high queue dwell time events
    visitor_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    db.execute(text("""
        INSERT INTO visitors (id, store_id, first_seen, last_seen)
        VALUES (:id, 'ST1008', :t, :t)
    """), {"id": visitor_id, "t": now})
    
    # Join queue, stay for 500 seconds (limit is 240 seconds)
    db.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, dwell_time_seconds, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM5', :v, 'ZONE_DWELL', 'billing_queue', :t1, 500.0, 0.95),
            (:e2, 'ST1008', 'CAM5', :v, 'ZONE_EXIT', 'billing_queue', :t2, 500.0, 0.95)
    """), {
        "v": visitor_id,
        "e1": str(uuid.uuid4()), "t1": now - timedelta(minutes=8),
        "e2": str(uuid.uuid4()), "t2": now
    })
    db.commit()
    
    anomalies_response = client.get("/stores/ST1008/anomalies")
    assert anomalies_response.status_code == 200
    anoms = anomalies_response.json()
    
    # Check if a high Billing Queue Dwell Time anomaly was detected and flagged
    dwell_alerts = [a for a in anoms["anomalies"] if a["metric"] == "Billing Queue Dwell Time"]
    assert len(dwell_alerts) > 0
    assert dwell_alerts[0]["severity"] == "HIGH"


# ==============================================================================
# 6. Test Zero Purchases (Conversion Rate Edge Cases)
# ==============================================================================
def test_zero_purchases(client, db):
    visitor_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    db.execute(text("""
        INSERT INTO visitors (id, store_id, first_seen, last_seen)
        VALUES (:id, 'ST1008', :t, :t)
    """), {"id": visitor_id, "t": now})
    
    # Client enters and browses but never purchases (no transactions seeded)
    db.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, timestamp, confidence)
        VALUES (:e, 'ST1008', 'CAM3', :v, 'ENTRY', :t, 0.95)
    """), {"v": visitor_id, "e": str(uuid.uuid4()), "t": now})
    db.commit()
    
    metrics_service = MetricsService(db)
    metrics = metrics_service.get_all_metrics("ST1008")
    
    # Unique visitors = 1, Unique buyers = 0, Conversion Rate = 0.0%
    assert metrics["unique_visitors"] == 1
    assert metrics["unique_buyers"] == 0
    assert metrics["conversion_rate_percentage"] == 0.0


# ==============================================================================
# 7. Test API Event Ingestion & Re-ID Resolution
# ==============================================================================
def test_api_event_ingestion_and_reid(client, db):
    # Step A: Ingest an entry to register a visitor with visual embedding
    embedding = [0.5 if i % 2 == 0 else -0.5 for i in range(512)]
    
    payload1 = {
        "store_id": "ST1008",
        "camera_id": "CAM3",
        "local_tracker_id": 42,
        "event_type": "ENTRY",
        "zone_id": None,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "bounding_box": [120.0, 150.0, 240.0, 360.0],
        "detection_confidence": 0.92,
        "visual_embedding": embedding
    }
    
    r1 = client.post("/events/ingest", json=payload1)
    assert r1.status_code == 201
    visitor_id = r1.json()["resolved_visitor_id"]
    
    # Step B: Ingest a second event (skincare entry) with similar embedding
    # A slight noise is added to check Re-ID matching threshold
    noisy_embedding = [x + 0.01 for x in embedding]
    
    payload2 = {
        "store_id": "ST1008",
        "camera_id": "CAM1",
        "local_tracker_id": 43,
        "event_type": "ZONE_ENTER",
        "zone_id": "skincare",
        "timestamp": (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat().replace("+00:00", "Z"),
        "bounding_box": [150.0, 200.0, 280.0, 410.0],
        "detection_confidence": 0.89,
        "visual_embedding": noisy_embedding
    }
    
    r2 = client.post("/events/ingest", json=payload2)
    assert r2.status_code == 201
    resolved_visitor_id = r2.json()["resolved_visitor_id"]
    
    # Verification: should match and map to the exact same visitor ID profile
    assert resolved_visitor_id == visitor_id


# ==============================================================================
# 8. Test Metrics Endpoint Dynamics
# ==============================================================================
def test_metrics_endpoint(client, db):
    # Seed a visitor, a queue join, and a checkout transaction to calculate conversion rate
    visitor_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    db.execute(text("""
        INSERT INTO visitors (id, store_id, first_seen, last_seen)
        VALUES (:id, 'ST1008', :t, :t)
    """), {"id": visitor_id, "t": now})
    
    db.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', :t1, 0.95),
            (:e2, 'ST1008', 'CAM5', :v, 'BILLING_QUEUE_JOIN', :t2, 0.95)
    """), {
        "v": visitor_id,
        "e1": str(uuid.uuid4()), "t1": now - timedelta(minutes=5),
        "e2": str(uuid.uuid4()), "t2": now - timedelta(minutes=2)
    })
    
    db.execute(text("""
        INSERT INTO transactions (id, store_id, visitor_id, pos_transaction_id, amount, timestamp)
        VALUES (:tx, 'ST1008', :v, 'POS-999', 150.0, :tx_time)
    """), {
        "v": visitor_id,
        "tx": str(uuid.uuid4()),
        "tx_time": now
    })
    db.commit()
    
    response = client.get("/stores/ST1008/metrics")
    assert response.status_code == 200
    res_json = response.json()
    
    assert res_json["store_id"] == "ST1008"
    assert res_json["metrics"]["total_unique_visitors"] == 1
    assert res_json["metrics"]["unique_buyers"] == 1
    assert res_json["metrics"]["conversion_rate_percentage"] == 100.0


# ==============================================================================
# 9. Test Funnel Endpoint
# ==============================================================================
def test_funnel_endpoint(client, db):
    # Setup one converted visitor to verify dynamic DB computation output
    visitor_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    db.execute(text("""
        INSERT INTO visitors (id, store_id, first_seen, last_seen)
        VALUES (:id, 'ST1008', :t, :t)
    """), {"id": visitor_id, "t": now})
    
    db.execute(text("""
        INSERT INTO events (id, store_id, camera_id, visitor_id, event_type, zone_id, timestamp, confidence)
        VALUES 
            (:e1, 'ST1008', 'CAM3', :v, 'ENTRY', NULL, :t1, 0.95),
            (:e2, 'ST1008', 'CAM1', :v, 'ZONE_ENTER', 'skincare', :t2, 0.95),
            (:e3, 'ST1008', 'CAM5', :v, 'BILLING_QUEUE_JOIN', 'billing_queue', :t3, 0.95)
    """), {
        "v": visitor_id,
        "e1": str(uuid.uuid4()), "t1": now - timedelta(minutes=5),
        "e2": str(uuid.uuid4()), "t2": now - timedelta(minutes=4),
        "e3": str(uuid.uuid4()), "t3": now - timedelta(minutes=2)
    })
    
    db.execute(text("""
        INSERT INTO transactions (id, store_id, visitor_id, pos_transaction_id, amount, timestamp)
        VALUES (:tx, 'ST1008', :v, 'POS-777', 89.90, :tx_time)
    """), {
        "v": visitor_id,
        "tx": str(uuid.uuid4()),
        "tx_time": now
    })
    db.commit()
    
    response = client.get("/stores/ST1008/funnel")
    assert response.status_code == 200
    funnel = response.json()
    
    assert funnel["data_source"] == "production_database"
    assert len(funnel["stages"]) == 4
    
    stages = {s["stage"]: s for s in funnel["stages"]}
    assert stages["1_Entry"]["count"] == 1
    assert stages["2_Zone_Interaction"]["count"] == 1
    assert stages["3_Billing_Queue_Join"]["count"] == 1
    assert stages["4_Purchase_Complete"]["count"] == 1
