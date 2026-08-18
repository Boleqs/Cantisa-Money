"""add subscription price history

Revision ID: d4f1b8e6a723
Revises: c7f4a1e9b3d6
Create Date: 2026-08-19 12:00:00.000000

Historique de prix daté par abonnement (`subscription_price_history`), pour que le rattrapage du
scheduler (`execute_due_subscriptions`) facture chaque échéance manquée au prix réellement en
vigueur à sa date plutôt qu'au prix actuel de l'abonnement — voir scheduler.py/rt_subscriptions.py.
`subscriptions.amount` reste le prix courant (dénormalisé, synchronisé depuis cet historique).
Backfill : une ligne par abonnement existant (date de création, montant actuel) pour qu'aucun
abonnement ne se retrouve sans historique après la migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd4f1b8e6a723'
down_revision: Union[str, Sequence[str], None] = 'c7f4a1e9b3d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'subscription_price_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_subscription_price_history'),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name='fk_subscription_price_history_user_id_users', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['subscription_id'], ['subscriptions.id'],
            name='fk_subscription_price_history_subscription_id_subscriptions', ondelete='CASCADE'),
        sa.UniqueConstraint(
            'subscription_id', 'effective_date', name='uq_subscription_price_history_subscription_id_effective_date'),
    )

    op.execute("""
        INSERT INTO subscription_price_history (id, user_id, subscription_id, effective_date, amount)
        SELECT gen_random_uuid(), user_id, id, created_at::date, amount
        FROM subscriptions
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('subscription_price_history')
