-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. Stores (Alphanumeric IDs supported)
CREATE TABLE IF NOT EXISTS stores (
    id VARCHAR(100) PRIMARY KEY, -- e.g., 'ST1008', 'ST1009'
    name VARCHAR(255) NOT NULL,
    address TEXT,
    timezone VARCHAR(100) DEFAULT 'UTC',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Cameras
CREATE TABLE IF NOT EXISTS cameras (
    id VARCHAR(50) PRIMARY KEY, -- CAM1, CAM2, CAM3, CAM4, CAM5
    store_id VARCHAR(100) NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    camera_type VARCHAR(50) NOT NULL, -- 'ENTRY_EXIT', 'ZONE', 'BILLING', 'STAFF'
    config JSONB, -- coordinates for tripwires or zones
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Visitors
CREATE TABLE IF NOT EXISTS visitors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id VARCHAR(100) NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    embedding vector(512),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- HNSW Vector Index for Cosine Distance search
CREATE INDEX IF NOT EXISTS idx_visitors_reid_hnsw 
ON visitors 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- 4. Events
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id VARCHAR(100) NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    camera_id VARCHAR(50) NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    visitor_id UUID REFERENCES visitors(id) ON DELETE SET NULL,
    local_tracker_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- ENTRY, EXIT, REENTRY, ZONE_ENTER, ZONE_EXIT, etc.
    zone_id VARCHAR(100), -- skincare, makeup, billing_queue
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    dwell_time_seconds REAL,
    bbox_x1 REAL,
    bbox_y1 REAL,
    bbox_x2 REAL,
    bbox_y2 REAL,
    confidence REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for analytical reports
CREATE INDEX IF NOT EXISTS idx_events_store_time ON events (store_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_visitor_time ON events (visitor_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type_zone ON events (event_type, zone_id);

-- 5. POS Transactions
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_id VARCHAR(100) NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    visitor_id UUID REFERENCES visitors(id) ON DELETE SET NULL,
    pos_transaction_id VARCHAR(100) UNIQUE NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    register_id VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_transactions_store_time ON transactions (store_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_visitor ON transactions (visitor_id);

-- Seed Initial Default Store
INSERT INTO stores (id, name, address, timezone)
VALUES 
    ('8bfa51c8-27db-4e9b-b9f8-132d7c956102', 'Downtown Flagship', '123 Retail Blvd, Metropolis', 'UTC'),
    ('ST1008', 'Brigade Road Store', 'Brigade Road, Bangalore', 'UTC')
ON CONFLICT (id) DO NOTHING;

-- Seed Cameras for ST1008 and default store
INSERT INTO cameras (id, store_id, name, camera_type, config)
VALUES 
    ('CAM3', 'ST1008', 'Entry Camera', 'ENTRY_EXIT', '{"tripwire": [[0, 240], [640, 240]]}'),
    ('CAM1', 'ST1008', 'Skincare Zone Camera', 'ZONE', '{"polygons": {"skincare": [[100, 100], [300, 100], [300, 400], [100, 400]]}}'),
    ('CAM2', 'ST1008', 'Makeup Zone Camera', 'ZONE', '{"polygons": {"makeup": [[50, 50], [250, 50], [250, 350], [50, 350]]}}'),
    ('CAM5', 'ST1008', 'Billing Counter Camera', 'BILLING', '{"polygons": {"billing_queue": [[200, 200], [500, 200], [500, 480], [200, 480]]}}')
ON CONFLICT DO NOTHING;
