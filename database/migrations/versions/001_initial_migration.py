"""initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-01 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector and uuid extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"vector\";")

    # 2. Create stores table
    op.create_table(
        'stores',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('timezone', sa.String(length=100), server_default='UTC'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Create cameras table
    op.create_table(
        'cameras',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('store_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('camera_type', sa.String(length=50), nullable=False),
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. Create visitors table
    op.create_table(
        'visitors',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', sa.String(length=100), nullable=False),
        sa.Column('first_seen', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('last_seen', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('embedding', Vector(512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    # HNSW Index on visitor embedding
    op.execute("CREATE INDEX IF NOT EXISTS idx_visitors_reid_hnsw ON visitors USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);")

    # 5. Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', sa.String(length=100), nullable=False),
        sa.Column('visitor_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_dwell_seconds', sa.Float(), nullable=True),
        sa.Column('is_staff', sa.Boolean(), server_default='false'),
        sa.Column('converted', sa.Boolean(), server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['visitor_id'], ['visitors.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('total_dwell_seconds >= 0', name='check_positive_dwell_seconds')
    )
    op.create_index('idx_sessions_store_time', 'sessions', ['store_id', 'start_time'])
    op.create_index('idx_sessions_visitor', 'sessions', ['visitor_id'])

    # 6. Create events table
    op.create_table(
        'events',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', sa.String(length=100), nullable=False),
        sa.Column('camera_id', sa.String(length=50), nullable=False),
        sa.Column('visitor_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('local_tracker_id', sa.String(length=50), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('zone_id', sa.String(length=100), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dwell_time_seconds', sa.Float(), nullable=True),
        sa.Column('bbox_x1', sa.Float(), nullable=True),
        sa.Column('bbox_y1', sa.Float(), nullable=True),
        sa.Column('bbox_x2', sa.Float(), nullable=True),
        sa.Column('bbox_y2', sa.Float(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['visitor_id'], ['visitors.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0', name='check_valid_confidence')
    )
    op.create_index('idx_events_store_timestamp', 'events', ['store_id', 'timestamp'])
    op.create_index('idx_events_visitor', 'events', ['visitor_id'])
    op.create_index('idx_events_type_zone', 'events', ['event_type', 'zone_id'])

    # 7. Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', sa.String(length=100), nullable=False),
        sa.Column('visitor_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('pos_transaction_id', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('register_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['visitor_id'], ['visitors.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pos_transaction_id'),
        sa.CheckConstraint('amount >= 0', name='check_positive_amount')
    )
    op.create_index('idx_transactions_store_time', 'transactions', ['store_id', 'timestamp'])
    op.create_index('idx_transactions_visitor', 'transactions', ['visitor_id'])

    # 8. Create anomalies table
    op.create_table(
        'anomalies',
        sa.Column('id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('store_id', sa.String(length=100), nullable=False),
        sa.Column('metric', sa.String(length=100), nullable=False),
        sa.Column('observed_value', sa.String(length=100), nullable=False),
        sa.Column('threshold_limit', sa.String(length=100), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_anomalies_store_time', 'anomalies', ['store_id', 'timestamp'])


def downgrade() -> None:
    op.drop_index('idx_anomalies_store_time', table_name='anomalies')
    op.drop_table('anomalies')
    op.drop_index('idx_transactions_visitor', table_name='transactions')
    op.drop_index('idx_transactions_store_time', table_name='transactions')
    op.drop_table('transactions')
    op.drop_index('idx_events_type_zone', table_name='events')
    op.drop_index('idx_events_visitor', table_name='events')
    op.drop_index('idx_events_store_timestamp', table_name='events')
    op.drop_table('events')
    op.drop_index('idx_sessions_visitor', table_name='sessions')
    op.drop_index('idx_sessions_store_time', table_name='sessions')
    op.drop_table('sessions')
    op.execute("DROP INDEX IF EXISTS idx_visitors_reid_hnsw;")
    op.drop_table('visitors')
    op.drop_table('cameras')
    op.drop_table('stores')
