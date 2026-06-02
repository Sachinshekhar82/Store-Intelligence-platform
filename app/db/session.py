import os
import json
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Set up logging
logger = logging.getLogger("store_intelligence.db")
logger.setLevel(logging.INFO)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password123@localhost:5432/store_intelligence")

engine = None
is_sqlite_fallback = False

try:
    # Test connection with a fast timeout (3 seconds) to check PostgreSQL availability
    if "postgresql" in DATABASE_URL:
        # Create temporary engine to test connection
        temp_engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 3})
        with temp_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # If connection test succeeded, initialize full PostgreSQL engine
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=10
        )
        logger.info("Connected to production PostgreSQL database successfully.")
except Exception as e:
    logger.warning(f"Unable to connect to PostgreSQL database ({str(e)}). Falling back to SQLite local database.")
if engine is None:
    # Fallback to local SQLite database in project directory (portable relative path)
    is_sqlite_fallback = True
    sqlite_url = "sqlite:///store_intelligence.db"
    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False}  # Safe multi-threaded SQLite access for FastAPI
    )
    logger.info(f"Initialized SQLite database fallback at {sqlite_url}")

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency injection helper
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auto-table creation and seeding logic (highly critical for clean bootstrap on SQLite fallbacks)
def bootstrap_database():
    from app.db.base import Base
    # Force import models to register tables on Base metadata
    from app.models.database import Store, Camera, Visitor, StoreSession, Event, Transaction, Anomaly
    
    if is_sqlite_fallback:
        try:
            # Create tables dynamically on SQLite file if not present
            Base.metadata.create_all(bind=engine)
            logger.info("Dynamic SQLite tables initialized successfully.")
            
            # Seed default store and camera details
            db = SessionLocal()
            try:
                store_exists = db.execute(text("SELECT 1 FROM stores WHERE id = 'ST1008'")).fetchone()
                if not store_exists:
                    db.execute(text("""
                        INSERT INTO stores (id, name, address, timezone)
                        VALUES ('ST1008', 'Brigade Road Store', 'Brigade Road, Bangalore', 'UTC')
                    """))
                    db.execute(text("""
                        INSERT INTO cameras (id, store_id, name, camera_type, config)
                        VALUES 
                            ('CAM3', 'ST1008', 'Entry Camera', 'ENTRY_EXIT', '{"tripwire": [[0, 240], [640, 240]]}'),
                            ('CAM1', 'ST1008', 'Skincare Zone Camera', 'ZONE', '{"polygons": {"skincare": [[100, 100], [300, 100], [300, 400], [100, 400]]}}'),
                            ('CAM2', 'ST1008', 'Makeup Zone Camera', 'ZONE', '{"polygons": {"makeup": [[50, 50], [250, 50], [250, 350], [50, 350]]}}'),
                            ('CAM5', 'ST1008', 'Billing Counter Camera', 'BILLING', '{"polygons": {"billing_queue": [[200, 200], [500, 200], [500, 480], [200, 480]]}}')
                    """))
                    db.commit()
                    logger.info("Successfully seeded SQLite database with default store and cameras.")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error during SQLite database bootstrap: {str(e)}", exc_info=True)

# Run bootstrap check on initialization
bootstrap_database()
