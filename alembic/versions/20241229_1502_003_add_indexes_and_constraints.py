"""add_indexes_and_constraints

Revision ID: 003_add_indexes
Revises: 002_create_customers
Create Date: 2024-12-29 15:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_add_indexes'
down_revision: Union[str, None] = '002_create_customers'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    # Create indexes for customers table
    op.create_index('idx_customers_tenant_id', 'customers', ['tenant_id'])
    op.create_index('idx_customers_external_id', 'customers', ['tenant_id', 'external_id'])
    op.create_index('idx_customers_email', 'customers', ['tenant_id', 'email'])
    op.create_index('idx_customers_is_active', 'customers', ['tenant_id', 'is_active'])


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_index('idx_customers_is_active', table_name='customers')
    op.drop_index('idx_customers_email', table_name='customers')
    op.drop_index('idx_customers_external_id', table_name='customers')
    op.drop_index('idx_customers_tenant_id', table_name='customers')
