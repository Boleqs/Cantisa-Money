"""add onboarding_completed flag

Revision ID: b1e5c9d3a7f2
Revises: 6b3d8f2a9c1e
Create Date: 2026-07-24 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1e5c9d3a7f2'
down_revision: Union[str, Sequence[str], None] = '6b3d8f2a9c1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user_settings', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.alter_column('user_settings', 'onboarding_completed', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_settings', 'onboarding_completed')
