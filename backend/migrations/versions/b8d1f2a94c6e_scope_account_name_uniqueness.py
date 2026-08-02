"""scope account name uniqueness to parent/institution

Revision ID: b8d1f2a94c6e
Revises: a3c7e4f1b829
Create Date: 2026-08-02 12:00:00.000000

Remplace l'unicité globale du nom de compte par utilisateur (accounts_user_id_name_key) par deux
contraintes scopées : unique parmi les comptes partageant le même compte parent, et unique parmi
ceux partageant la même institution. Un compte sans parent ni institution n'est plus protégé par
aucune des deux — voir le commentaire dans backend/database/models/accounts.py et rt_accounts.py
(vérification applicative correspondante, la contrainte DB seule ne donnerait qu'une erreur brute).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b8d1f2a94c6e'
down_revision: Union[str, Sequence[str], None] = 'a3c7e4f1b829'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('accounts_user_id_name_key', 'accounts', type_='unique')
    op.create_unique_constraint(
        'uq_accounts_user_parent_name', 'accounts', ['user_id', 'parent_id', 'name'])
    op.create_unique_constraint(
        'uq_accounts_user_institution_name', 'accounts', ['user_id', 'institution_id', 'name'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_accounts_user_institution_name', 'accounts', type_='unique')
    op.drop_constraint('uq_accounts_user_parent_name', 'accounts', type_='unique')
    op.create_unique_constraint('accounts_user_id_name_key', 'accounts', ['user_id', 'name'])
