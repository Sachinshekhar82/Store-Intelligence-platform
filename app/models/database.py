import uuid
import json
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Boolean,
    Float,
    DateTime,
    Numeric,
    ForeignKey,
    Index,
    CheckConstraint,
    UniqueConstraint
)
from sqlalchemy.types import TypeDecorator, NullType
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base

class SafeJSON(TypeDecorator):
    impl = NullType
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from sqlalchemy.dialects.postgresql import JSONB
                return dialect.type_descriptor(JSONB)
            except ImportError:
                from sqlalchemy import JSON
                return dialect.type_descriptor(JSON)
        else:
            from sqlalchemy import JSON
            return dialect.type_descriptor(JSON)

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value

class SafeVector(TypeDecorator):
    impl = NullType
    cache_ok = True

    def __init__(self, size):
        super().__init__()
        self.size = size

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(self.size))
            except ImportError:
                return dialect.type_descriptor(String)
        else:
            return dialect.type_descriptor(String)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        else:
            try:
                return json.loads(value)
            except Exception:
                val_str = str(value).strip('[]')
                if val_str:
                    return [float(x) for x in val_str.split(',')]
                return []

class Store(Base):
    __tablename__ = "stores"
    
    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    address = Column(String, nullable=True)
    timezone = Column(String(100), default="UTC")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    cameras = relationship("Camera", back_populates="store", cascade="all, delete-orphan")
    visitors = relationship("Visitor", back_populates="store", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="store", cascade="all, delete-orphan")
    sessions = relationship("StoreSession", back_populates="store", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="store", cascade="all, delete-orphan")
    anomalies = relationship("Anomaly", back_populates="store", cascade="all, delete-orphan")


class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(String(50), primary_key=True)
    store_id = Column(String(100), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    camera_type = Column(String(50), nullable=False)  # ENTRY_EXIT, ZONE, BILLING, STAFF
    config = Column(SafeJSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="cameras")
    events = relationship("Event", back_populates="camera", cascade="all, delete-orphan")


class Visitor(Base):
    __tablename__ = "visitors"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(String(100), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    first_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    embedding = Column(SafeVector(512), nullable=True) # pgvector visual embedding signature
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="visitors")
    events = relationship("Event", back_populates="visitor")
    sessions = relationship("StoreSession", back_populates="visitor")
    transactions = relationship("Transaction", back_populates="visitor")


class StoreSession(Base):
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(String(100), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    visitor_id = Column(UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="SET NULL"), nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    total_dwell_seconds = Column(Float, nullable=True)
    is_staff = Column(Boolean, default=False)
    converted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="sessions")
    visitor = relationship("Visitor", back_populates="sessions")
    
    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint("total_dwell_seconds >= 0", name="check_positive_dwell_seconds"),
        Index("idx_sessions_store_time", "store_id", "start_time"),
        Index("idx_sessions_visitor", "visitor_id"),
    )


class Event(Base):
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(String(100), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    camera_id = Column(String(50), ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    visitor_id = Column(UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="SET NULL"), nullable=True)
    local_tracker_id = Column(String(50), nullable=True)  # ByteTrack tracker ID
    event_type = Column(String(50), nullable=False)  # ENTRY, EXIT, ZONE_ENTER, etc.
    zone_id = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    dwell_time_seconds = Column(Float, nullable=True)
    bbox_x1 = Column(Float, nullable=True)
    bbox_y1 = Column(Float, nullable=True)
    bbox_x2 = Column(Float, nullable=True)
    bbox_y2 = Column(Float, nullable=True)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="events")
    camera = relationship("Camera", back_populates="events")
    visitor = relationship("Visitor", back_populates="events")
    
    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="check_valid_confidence"),
        Index("idx_events_store_timestamp", "store_id", "timestamp"),
        Index("idx_events_visitor", "visitor_id"),
        Index("idx_events_type_zone", "event_type", "zone_id"),
    )


class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(String(100), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    visitor_id = Column(UUID(as_uuid=True), ForeignKey("visitors.id", ondelete="SET NULL"), nullable=True)
    pos_transaction_id = Column(String(100), unique=True, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    register_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="transactions")
    visitor = relationship("Visitor", back_populates="transactions")
    
    # Constraints & Indexes
    __table_args__ = (
        CheckConstraint("amount >= 0", name="check_positive_amount"),
        Index("idx_transactions_store_time", "store_id", "timestamp"),
        Index("idx_transactions_visitor", "visitor_id"),
    )


class Anomaly(Base):
    __tablename__ = "anomalies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(String(100), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False)
    metric = Column(String(100), nullable=False)  # e.g., 'Conversion Rate Drop', 'Queue Dwell Time'
    observed_value = Column(String(100), nullable=False)
    threshold_limit = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH
    timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    store = relationship("Store", back_populates="anomalies")
    
    # Constraints & Indexes
    __table_args__ = (
        Index("idx_anomalies_store_time", "store_id", "timestamp"),
    )
