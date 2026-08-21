"""add asset possession/disposal fees

Revision ID: e6a2c8d4f710
Revises: d4f1b8e6a723
Create Date: 2026-08-20 09:00:00.000000

Frais/commissions associés à un achat ou une vente d'actif (`asset_possession.fees`,
`asset_disposal.fees`) — montant forfaitaire (pas un prix unitaire), toujours saisi dans la devise
par défaut de l'utilisateur (Settings.currency), quelle que soit la devise de l'actif, distinct de
purchase_price/sale_price pour ne pas polluer le prix unitaire affiché ailleurs (moyenne d'achat,
etc). Vient s'ajouter au montant réellement débité/crédité du compte bancaire (voir rt_assets.py,
reconverti au besoin via portfolio_ops.py::convert_asset_to_default_currency) et réduit le gain
réalisé (rt_assets.py::sell_possession, reconverti dans la devise de l'actif via
convert_default_to_asset_currency), donc l'assiette PFU (rt_tax.py, qui lit directement
asset_disposal.realized_gain).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6a2c8d4f710'
down_revision: Union[str, Sequence[str], None] = 'd4f1b8e6a723'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_possession', sa.Column('fees', sa.Numeric(), nullable=False, server_default='0'))
    op.add_column('asset_disposal', sa.Column('fees', sa.Numeric(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('asset_disposal', 'fees')
    op.drop_column('asset_possession', 'fees')
