"""bank connections multi account linking

Revision ID: c7f4a1e9b3d6
Revises: a1c5e8f3d29b
Create Date: 2026-08-07 04:00:00.000000

Permet à une banque qui renvoie plusieurs comptes lors de l'autorisation de tous les proposer à la
liaison, au lieu de deviner et de ne lier que le premier. Ajoute le statut 'needs_linking' (compte
connu de la banque, pas encore mappé à un compte Cantisa) + des colonnes d'affichage pour aider
l'utilisateur à distinguer les comptes renvoyés (nom, devise) avant de choisir la liaison.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7f4a1e9b3d6'
down_revision: Union[str, Sequence[str], None] = 'a1c5e8f3d29b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bank_connections', sa.Column('external_account_name', sa.String(length=256), nullable=True))
    op.add_column('bank_connections', sa.Column('external_account_currency', sa.String(length=8), nullable=True))

    op.drop_constraint('ck_bank_connections_status', 'bank_connections', type_='check')
    op.create_check_constraint(
        'ck_bank_connections_status', 'bank_connections',
        "status IN ('pending', 'needs_linking', 'connected', 'error', 'expired')"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_bank_connections_status', 'bank_connections', type_='check')
    op.create_check_constraint(
        'ck_bank_connections_status', 'bank_connections',
        "status IN ('pending', 'connected', 'error', 'expired')"
    )
    op.drop_column('bank_connections', 'external_account_currency')
    op.drop_column('bank_connections', 'external_account_name')
