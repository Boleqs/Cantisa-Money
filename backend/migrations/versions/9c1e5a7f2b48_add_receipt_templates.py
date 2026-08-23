"""add receipt templates

Revision ID: 9c1e5a7f2b48
Revises: 6f2c8b1d4e93
Create Date: 2026-08-23 15:00:00.000000

Gabarits de ticket : zones dessinées par l'utilisateur sur un ticket photographié (marchand, date,
total, zone articles) pour guider l'OCR sur les prochains tickets du même marchand — recadrage +
OCR ciblé par zone au lieu d'une lecture pleine page + heuristiques. Voir
backend/utils/receipt_ocr.py::apply_template et backend/routes/rt_receipt_templates.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9c1e5a7f2b48'
down_revision: Union[str, Sequence[str], None] = '6f2c8b1d4e93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'receipt_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('merchant_name', sa.String(length=100), nullable=False),
        sa.Column('merchant_key', sa.String(length=100), nullable=False),
        sa.Column('zones', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'merchant_key'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('receipt_templates')
