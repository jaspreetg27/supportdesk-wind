"""create threads messages events

Revision ID: 20241230_1600_004
Revises: 20241229_1502_003
Create Date: 2024-12-30 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20241230_1600_004'
down_revision: Union[str, None] = '003_add_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enums using conditional SQL
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE thread_state AS ENUM ('new', 'acknowledged', 'in_progress', 'waiting_for_customer', 'needs_review', 'urgent', 'resolved', 'closed');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE message_type AS ENUM ('inbound', 'outbound', 'system');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE platform_type AS ENUM ('whatsapp', 'instagram', 'facebook', 'internal');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE actor_type AS ENUM ('system', 'user');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create tables using raw SQL to avoid enum issues
    op.execute("""
        CREATE TABLE threads (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            customer_id UUID NOT NULL REFERENCES customers(id),
            platform platform_type NOT NULL,
            platform_thread_id VARCHAR(255),
            state thread_state NOT NULL DEFAULT 'new',
            priority INTEGER NOT NULL DEFAULT 0,
            subject VARCHAR(500),
            metadata JSON NOT NULL DEFAULT '{}',
            last_message_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true,
            CONSTRAINT threads_priority_check CHECK (priority BETWEEN 0 AND 10),
            CONSTRAINT unique_platform_thread UNIQUE (tenant_id, platform, platform_thread_id) DEFERRABLE INITIALLY IMMEDIATE
        );
    """)
    
    op.execute("""
        CREATE TABLE messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            platform_message_id VARCHAR(255) NOT NULL,
            type message_type NOT NULL,
            content TEXT,
            metadata JSON NOT NULL DEFAULT '{}',
            sent_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true,
            CONSTRAINT unique_platform_message UNIQUE (thread_id, platform_message_id)
        );
    """)
    
    op.execute("""
        CREATE TABLE thread_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            thread_id UUID NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
            event_type VARCHAR(100) NOT NULL,
            old_state thread_state,
            new_state thread_state,
            actor_type actor_type NOT NULL DEFAULT 'system',
            actor_id VARCHAR(255),
            correlation_id UUID,
            metadata JSON NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true
        );
    """)

    # Create indexes
    op.create_index('idx_threads_tenant_state', 'threads', ['tenant_id', 'state'])
    op.create_index('idx_threads_tenant_customer', 'threads', ['tenant_id', 'customer_id'])
    op.create_index('idx_threads_last_message', 'threads', [sa.text('last_message_at DESC NULLS LAST'), sa.text('updated_at DESC'), sa.text('id DESC')])
    op.create_index('idx_threads_priority', 'threads', [sa.text('priority DESC'), sa.text('updated_at DESC')])
    
    op.create_index('idx_messages_thread_sent', 'messages', ['thread_id', 'sent_at'])
    op.create_index('idx_messages_thread_created', 'messages', ['thread_id', 'created_at'])
    
    op.create_index('idx_events_thread_created', 'thread_events', ['thread_id', sa.text('created_at DESC')])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_events_thread_created', table_name='thread_events')
    op.drop_index('idx_messages_thread_created', table_name='messages')
    op.drop_index('idx_messages_thread_sent', table_name='messages')
    op.drop_index('idx_threads_priority', table_name='threads')
    op.drop_index('idx_threads_last_message', table_name='threads')
    op.drop_index('idx_threads_tenant_customer', table_name='threads')
    op.drop_index('idx_threads_tenant_state', table_name='threads')

    # Drop tables
    op.drop_table('thread_events')
    op.drop_table('messages')
    op.drop_table('threads')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS actor_type')
    op.execute('DROP TYPE IF EXISTS platform_type')
    op.execute('DROP TYPE IF EXISTS message_type')
    op.execute('DROP TYPE IF EXISTS thread_state')
