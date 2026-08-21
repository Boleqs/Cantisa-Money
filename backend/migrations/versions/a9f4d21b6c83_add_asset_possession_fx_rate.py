"""add asset possession manual fx_rate

Revision ID: a9f4d21b6c83
Revises: e6a2c8d4f710
Create Date: 2026-08-20 11:00:00.000000

Taux de change saisi manuellement par l'utilisateur à l'achat d'un actif hors devise par défaut
(`asset_possession.fx_rate`, nullable — NULL signifie "résolu automatiquement", pas "taux de 1") :
1 unité de la devise de l'actif = fx_rate unité(s) de la devise par défaut (Settings.currency),
indépendamment du compte réellement débité. Persisté (pas juste utilisé au moment de l'achat) pour
pouvoir le réafficher/le reproposer à l'édition sans quoi une simple correction de quantité ferait
retomber silencieusement sur la résolution automatique et changerait le montant réellement débité
— et pour reconvertir plus tard, au bon taux historique, les frais d'achat de ce lot lors d'une
vente partielle (rt_assets.py::sell_possession). Voir rt_assets.py::add_possession/update_possession
et utils/portfolio_ops.py::convert_asset_to_default_currency/convert_default_to_asset_currency.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9f4d21b6c83'
down_revision: Union[str, Sequence[str], None] = 'e6a2c8d4f710'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_possession', sa.Column('fx_rate', sa.Numeric(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_possession', 'fx_rate')
