"""add account closing (is_closed / closed_at)

Revision ID: a3f7d9c1e5b6
Revises: c8f2e5a3b9d1
Create Date: 2026-07-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f7d9c1e5b6'
down_revision: Union[str, Sequence[str], None] = 'c8f2e5a3b9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('accounts', sa.Column('is_closed', sa.Boolean(), nullable=False, server_default='false'))
    op.alter_column('accounts', 'is_closed', server_default=None)
    op.add_column('accounts', sa.Column('closed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('accounts', 'closed_at')
    op.drop_column('accounts', 'is_closed')
