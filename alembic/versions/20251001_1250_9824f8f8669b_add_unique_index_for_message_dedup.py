"""add unique index for message dedup

Revision ID: 9824f8f8669b
Revises: 20241230_1600_004
Create Date: 2025-10-01 00:00:00
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "9824f8f8669b"
down_revision = "20241230_1600_004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_index(
        "ix_messages_thread_platform_unique",
        "messages",
        ["thread_id", "platform_message_id"],
        unique=True,
    )

def downgrade() -> None:
    op.drop_index("ix_messages_thread_platform_unique", table_name="messages")
