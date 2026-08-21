"""add asset disposal fx_rate

Revision ID: c3d9e7f1a204
Revises: a9f4d21b6c83
Create Date: 2026-08-21 10:00:00.000000

Taux de change effectivement appliqué à une vente d'actif hors devise par défaut
(`asset_disposal.fx_rate`, nullable — NULL si l'actif est dans la devise par défaut, aucune
conversion n'a de sens) : 1 unité de la devise de l'actif = fx_rate unité(s) de la devise par
défaut (Settings.currency), manuel si fourni par l'utilisateur sinon résolu automatiquement au
taux historique de la date de vente. Symétrique d'AssetPossession.fx_rate (voir migration
a9f4d21b6c83) — persisté pour la même raison : ne pas redépendre d'une résolution automatique
implicite a posteriori. Voir rt_assets.py::sell_possession et
utils/portfolio_ops.py::convert_asset_to_default_currency.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d9e7f1a204'
down_revision: Union[str, Sequence[str], None] = 'a9f4d21b6c83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_disposal', sa.Column('fx_rate', sa.Numeric(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_disposal', 'fx_rate')
