"""Add unique index for message deduplication

Revision ID: 5b744fc6ddf2
Revises: 20241230_1600_004
Create Date: 2025-09-30 23:04:55.222710

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5b744fc6ddf2"
down_revision: Union[str, None] = "20241230_1600_004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Add unique index for message deduplication
    op.create_index(
        'ix_messages_thread_platform_unique',
        'messages',
        ['thread_id', 'platform_message_id'],
        unique=True
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('ix_messages_thread_platform_unique', table_name='messages')
