"""add financial documents

Revision ID: f4a7c1e9b532
Revises: c3d9e7f1a204
Create Date: 2026-08-22 09:00:00.000000

Coffre-fort de documents financiers (`financial_documents`) — RIB, contrats d'assurance, avis
d'imposition, actes de propriété, contrats de prêt... Distinct de `transaction_documents` (toujours
rattaché à une transaction) : ici le rattachement à un compte/actif/prêt est optionnel (au plus un
des trois, imposé par la CheckConstraint `num_nonnulls`). Fichier stocké en base (LargeBinary),
comme `transaction_documents.file_data` — aucun stockage fichier/S3 n'existe ailleurs dans l'appli.
`extracted_text` (OCR, voir utils/receipt_ocr.py::extract_text) alimente la recherche dans le
contenu ; NULL si l'OCR échoue ou ne trouve rien, ce qui ne bloque jamais l'enregistrement du
document. Voir rt_financial_documents.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f4a7c1e9b532'
down_revision: Union[str, Sequence[str], None] = 'c3d9e7f1a204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'financial_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_filename', sa.String(length=256), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_data', sa.LargeBinary(), nullable=False),
        sa.Column('category', sa.String(length=30), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('linked_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('linked_asset_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('linked_loan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['linked_account_id'], ['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['linked_asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['linked_loan_id'], ['loans.id'], ondelete='SET NULL'),
        sa.CheckConstraint(
            'num_nonnulls(linked_account_id, linked_asset_id, linked_loan_id) <= 1',
            name='ck_financial_documents_single_link'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('financial_documents')
