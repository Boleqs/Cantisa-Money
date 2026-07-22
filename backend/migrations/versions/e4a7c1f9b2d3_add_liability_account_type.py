"""add liability account type

Revision ID: e4a7c1f9b2d3
Revises: 3d8f6a1b9c4e
Create Date: 2026-07-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e4a7c1f9b2d3'
down_revision: Union[str, Sequence[str], None] = '3d8f6a1b9c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Le nom de la contrainte CHECK sur account_type n'est pas fixé dans le modèle (créée
    # unnamed dans 0bee1c5b7470_initial_schema.py) — Postgres lui attribue un nom généré
    # automatiquement, potentiellement différent d'un environnement à l'autre. On la retrouve
    # dynamiquement via pg_constraint plutôt que de deviner son nom, en la distinguant de l'autre
    # CHECK de la table (account_subtype) par la présence du motif "account_type" sans
    # "account_subtype" dans sa définition. Attention : Postgres réécrit "x IN (...)" en
    # "x = ANY (ARRAY[...])" dans pg_get_constraintdef — ne jamais chercher le littéral "IN".
    op.execute("""
        DO $$
        DECLARE
            existing_constraint text;
        BEGIN
            SELECT conname INTO existing_constraint
            FROM pg_constraint
            WHERE conrelid = 'accounts'::regclass
              AND contype = 'c'
              AND pg_get_constraintdef(oid) LIKE '%account_type%'
              AND pg_get_constraintdef(oid) NOT LIKE '%account_subtype%';

            IF existing_constraint IS NOT NULL THEN
                EXECUTE format('ALTER TABLE accounts DROP CONSTRAINT %I', existing_constraint);
            END IF;
        END $$;
    """)
    op.execute("""
        ALTER TABLE accounts ADD CONSTRAINT accounts_account_type_check
        CHECK (account_type IN ('Income', 'Expense', 'Equity', 'Assets', 'Current', 'Liability'))
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Échoue si des comptes 'Liability' existent encore (comportement attendu pour tout
    # downgrade qui retire une valeur de type en usage).
    op.execute("ALTER TABLE accounts DROP CONSTRAINT accounts_account_type_check")
    op.execute("""
        ALTER TABLE accounts ADD CHECK
        (account_type IN ('Income', 'Expense', 'Equity', 'Assets', 'Current'))
    """)
