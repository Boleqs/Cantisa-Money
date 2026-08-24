"""add sale_id grouping column to asset_disposal

Revision ID: a1c7d9e4f213
Revises: fb3f834c0962
Create Date: 2026-08-24 10:00:00.000000

Permet de modifier/supprimer une vente comme une position d'achat, y compris quand elle a puisé
sur plusieurs lots à la fois (FIFO) — voir backend/routes/rt_assets.py::_execute_sale. Toutes les
cessions générées par un même appel à sell_possession partagent désormais le même sale_id.

Backfill des cessions existantes (operation_id IS NULL, une cession issue d'une fusion n'est pas
une vente éditable ici) : celles qui partagent un tx_id (vente avec compte crédité) sont regroupées
sous un même sale_id nouvellement généré ; celles sans tx_id (vente sans écriture comptable) n'ont
aucune autre clé de corrélation fiable, chacune reçoit donc son propre sale_id — au pire une vente
ancienne qui avait touché plusieurs lots sans compte crédité s'éditera lot par lot comme aujourd'hui,
au lieu d'être regroupée.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1c7d9e4f213'
down_revision: Union[str, Sequence[str], None] = 'fb3f834c0962'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('asset_disposal', sa.Column('sale_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_asset_disposal_sale_id', 'asset_disposal', ['sale_id'])

    conn = op.get_bind()

    tx_ids = conn.execute(sa.text(
        "SELECT DISTINCT tx_id FROM asset_disposal WHERE operation_id IS NULL AND tx_id IS NOT NULL"
    )).scalars().all()
    for tx_id in tx_ids:
        conn.execute(
            sa.text("UPDATE asset_disposal SET sale_id = :sale_id WHERE tx_id = :tx_id AND operation_id IS NULL"),
            {'sale_id': str(uuid.uuid4()), 'tx_id': tx_id},
        )

    orphan_ids = conn.execute(sa.text(
        "SELECT id FROM asset_disposal WHERE operation_id IS NULL AND tx_id IS NULL AND sale_id IS NULL"
    )).scalars().all()
    for disposal_id in orphan_ids:
        conn.execute(
            sa.text("UPDATE asset_disposal SET sale_id = :sale_id WHERE id = :id"),
            {'sale_id': str(uuid.uuid4()), 'id': disposal_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_asset_disposal_sale_id', table_name='asset_disposal')
    op.drop_column('asset_disposal', 'sale_id')
