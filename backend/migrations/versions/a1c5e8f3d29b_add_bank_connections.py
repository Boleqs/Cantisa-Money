"""add bank connections

Revision ID: a1c5e8f3d29b
Revises: f2a6c9d13b7e
Create Date: 2026-08-07 10:00:00.000000

Ajoute la table bank_connections (synchro bancaire automatique, phase 1 : Enable Banking) et la
colonne accounts.external_account_uid qui relie un compte Cantisa à l'identifiant de compte renvoyé
par le fournisseur externe. Schéma pensé pour accueillir plusieurs fournisseurs à terme (colonne
aspsp_name/aspsp_country génériques, pas de champ spécifique à Enable Banking) — voir aussi les
colonnes déjà génériques de institutions.sync_provider (migration 870fbb76215a).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1c5e8f3d29b'
down_revision: Union[str, Sequence[str], None] = 'f2a6c9d13b7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'bank_connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('institution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True),
        # Nom technique du fournisseur ('enable_banking'...), pas affiché tel quel à l'utilisateur.
        sa.Column('sync_provider', sa.String(length=64), nullable=False),
        sa.Column('aspsp_name', sa.String(length=256), nullable=False),
        sa.Column('aspsp_country', sa.String(length=8), nullable=False),
        # État CSRF de la demande d'autorisation en cours, le temps du round-trip banque -> callback.
        # Consommé (mis à NULL) dès l'échange réussi contre une session.
        sa.Column('state', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', sa.String(length=256), nullable=True),
        sa.Column('external_account_uid', sa.String(length=256), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_bank_connections'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                 name='fk_bank_connections_user_id_users', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['institution_id'], ['institutions.id'],
                                 name='fk_bank_connections_institution_id_institutions',
                                 ondelete='SET NULL', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'],
                                 name='fk_bank_connections_account_id_accounts',
                                 ondelete='SET NULL', onupdate='CASCADE'),
        sa.UniqueConstraint('id', name='uq_bank_connections_id'),
        sa.UniqueConstraint('state', name='uq_bank_connections_state'),
        sa.CheckConstraint("status IN ('pending', 'connected', 'error', 'expired')",
                            name='ck_bank_connections_status'),
    )

    op.add_column('accounts', sa.Column('external_account_uid', sa.String(length=256), nullable=True))
    op.create_unique_constraint(
        'uq_accounts_user_external_account_uid', 'accounts', ['user_id', 'external_account_uid']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_accounts_user_external_account_uid', 'accounts', type_='unique')
    op.drop_column('accounts', 'external_account_uid')
    op.drop_table('bank_connections')
