"""add import category rules

Revision ID: f2a6c9d13b7e
Revises: c4a9e7d2f150
Create Date: 2026-08-05 10:00:00.000000

Ajoute la table import_category_rules : mémorise, par utilisateur, la catégorie et le compte de
contrepartie associés à un libellé de transaction normalisé (minuscules, sans accents/chiffres).
Remplace la catégorisation par IA lors de l'import (routes /api/ai/* supprimées) — les règles sont
apprises automatiquement à partir des choix de l'utilisateur lors de la confirmation d'un import,
et réappliquées aux imports suivants sans dépendance à un service externe.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f2a6c9d13b7e'
down_revision: Union[str, Sequence[str], None] = 'c4a9e7d2f150'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'import_category_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('keyword', sa.String(length=255), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('opposing_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_import_category_rules'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                 name='fk_import_category_rules_user_id_users', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'],
                                 name='fk_import_category_rules_category_id_categories',
                                 ondelete='SET NULL', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['opposing_account_id'], ['accounts.id'],
                                 name='fk_import_category_rules_opposing_account_id_accounts',
                                 ondelete='SET NULL', onupdate='CASCADE'),
        sa.UniqueConstraint('user_id', 'keyword', name='uq_import_category_rules_user_id_keyword'),
        sa.UniqueConstraint('id', name='uq_import_category_rules_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('import_category_rules')
