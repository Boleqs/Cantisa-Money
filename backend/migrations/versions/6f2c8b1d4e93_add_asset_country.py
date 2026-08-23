"""add asset country

Revision ID: 6f2c8b1d4e93
Revises: 84e0f7331483
Create Date: 2026-08-23 12:00:00.000000

Pays d'un actif physique (RealEstate/Vehicle/Other), saisi manuellement — pour Stock/ETF, la
géographie est déjà dérivée dynamiquement via Yahoo Finance (voir backend/utils/asset_geography.py),
country reste NULL. Nom de pays en anglais (convention yfinance) pour fusionner correctement avec
cette source dans /api/assets/geography sans dupliquer un même pays sous deux libellés — voir
rt_assets.py::get_assets_geography.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f2c8b1d4e93'
down_revision: Union[str, Sequence[str], None] = '84e0f7331483'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('assets', sa.Column('country', sa.String(length=100), nullable=True))
    op.create_check_constraint(
        'assets_country_physical_only', 'assets',
        "asset_type NOT IN ('Stock', 'ETF') OR country IS NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('assets_country_physical_only', 'assets', type_='check')
    op.drop_column('assets', 'country')
