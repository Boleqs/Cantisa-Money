"""add financial documents file_size

Revision ID: 84e0f7331483
Revises: f4a7c1e9b532
Create Date: 2026-08-22 09:30:00.000000

Taille en octets du document, dénormalisée depuis `file_data` (calculée à l'ajout, voir
rt_financial_documents.py) — évite de rapatrier le blob complet côté Python juste pour afficher
une taille dans la liste (stat "Espace utilisé" du Dossier financier).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84e0f7331483'
down_revision: Union[str, Sequence[str], None] = 'f4a7c1e9b532'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('financial_documents', sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('financial_documents', 'file_size')
