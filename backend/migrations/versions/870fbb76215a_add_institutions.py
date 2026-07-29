"""add institutions

Revision ID: 870fbb76215a
Revises: 15d48a123464
Create Date: 2026-07-28 19:11:56.024069

Ajout d'une entité "Institution bancaire" (nom, BIC, site web, notes, couleur) rattachée aux
comptes, plus des colonnes de statut génériques et inertes pour une future connectivité de
synchro bancaire externe (aucun provider branché, aucun secret stocké). Contrairement à la
migration initiale (dump SQL brut à cause des triggers custom), celle-ci est un ajout simple
sans trigger : opérations Alembic standards.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '870fbb76215a'
down_revision: Union[str, Sequence[str], None] = '15d48a123464'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'institutions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('bic', sa.String(length=32), nullable=True),
        sa.Column('website', sa.String(length=256), nullable=True),
        sa.Column('notes', sa.String(length=1024), nullable=True),
        sa.Column('color', sa.String(length=16), nullable=False),
        sa.Column('sync_provider', sa.String(length=64), nullable=True),
        sa.Column('external_institution_id', sa.String(length=128), nullable=True),
        sa.Column('connection_id', sa.String(length=128), nullable=True),
        sa.Column('sync_status', sa.String(length=32), nullable=False),
        sa.Column('sync_enabled', sa.Boolean(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_institutions'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_institutions_user_id_users', ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'name', name='uq_institutions_user_id_name'),
        sa.UniqueConstraint('id', name='uq_institutions_id'),
        sa.CheckConstraint(
            "color IN ('green', 'red', 'blue', 'white', 'black', 'yellow', 'purple')",
            name='ck_institutions_color'),
        sa.CheckConstraint(
            "sync_status IN ('not_connected', 'connected', 'error', 'syncing')",
            name='ck_institutions_sync_status'),
    )

    op.add_column('accounts', sa.Column('institution_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_accounts_institution_id_institutions', 'accounts', 'institutions',
        ['institution_id'], ['id'], ondelete='SET NULL', onupdate='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_accounts_institution_id_institutions', 'accounts', type_='foreignkey')
    op.drop_column('accounts', 'institution_id')
    op.drop_table('institutions')
