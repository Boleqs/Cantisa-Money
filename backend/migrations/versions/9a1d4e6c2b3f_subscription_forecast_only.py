"""subscription forecast-only flag

Revision ID: 9a1d4e6c2b3f
Revises: 7c2f4a91d3ab
Create Date: 2026-07-13 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '9a1d4e6c2b3f'
down_revision: Union[str, Sequence[str], None] = '7c2f4a91d3ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('subscriptions', sa.Column('is_forecast_only', sa.Boolean(), nullable=False, server_default='false'))
    op.alter_column('subscriptions', 'is_forecast_only', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('subscriptions', 'is_forecast_only')
