"""account consolidated totals rollup

Revision ID: 7c2f4a91d3ab
Revises: 0bee1c5b7470
Create Date: 2026-07-13 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7c2f4a91d3ab'
down_revision: Union[str, Sequence[str], None] = '0bee1c5b7470'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('accounts', sa.Column('consolidated_earned', sa.Numeric(), nullable=False, server_default='0'))
    op.add_column('accounts', sa.Column('consolidated_spent', sa.Numeric(), nullable=False, server_default='0'))
    op.alter_column('accounts', 'consolidated_earned', server_default=None)
    op.alter_column('accounts', 'consolidated_spent', server_default=None)

    # Backfill : consolidated_* = somme de total_* sur le compte lui-même et tous ses
    # descendants (fermeture ancêtre/descendant via CTE récursive), pour les comptes
    # parent/enfant déjà existants avant cette migration.
    op.execute("""
        WITH RECURSIVE closure AS (
            SELECT id AS account_id, id AS ancestor_id FROM accounts
            UNION ALL
            SELECT c.account_id, a.parent_id
            FROM closure c
            JOIN accounts a ON a.id = c.ancestor_id
            WHERE a.parent_id IS NOT NULL
        ),
        rollup AS (
            SELECT cl.ancestor_id AS id,
                   SUM(a2.total_earned) AS earned,
                   SUM(a2.total_spent) AS spent
            FROM closure cl
            JOIN accounts a2 ON a2.id = cl.account_id
            GROUP BY cl.ancestor_id
        )
        UPDATE accounts SET
            consolidated_earned = rollup.earned,
            consolidated_spent = rollup.spent
        FROM rollup
        WHERE accounts.id = rollup.id
    """)

    # Remonte la chaîne parent_id depuis start_id jusqu'à la racine, recalculant à
    # chaque étape consolidated_* = total propre + somme des consolidated_* des
    # enfants directs (déjà à jour) — O(profondeur) par appel, pas O(sous-arbre).
    op.execute("""
    CREATE OR REPLACE FUNCTION propagate_consolidated_totals(start_id UUID)
    RETURNS VOID AS $$
    DECLARE
        current_id UUID := start_id;
        current_parent UUID;
        own_e NUMERIC;
        own_s NUMERIC;
        children_e NUMERIC;
        children_s NUMERIC;
        depth INT := 0;
    BEGIN
        WHILE current_id IS NOT NULL AND depth < 100 LOOP
            SELECT total_earned, total_spent, parent_id INTO own_e, own_s, current_parent
            FROM accounts WHERE id = current_id;

            IF NOT FOUND THEN
                EXIT;
            END IF;

            SELECT COALESCE(SUM(consolidated_earned), 0), COALESCE(SUM(consolidated_spent), 0)
            INTO children_e, children_s
            FROM accounts WHERE parent_id = current_id;

            UPDATE accounts
            SET consolidated_earned = own_e + children_e,
                consolidated_spent = own_s + children_s
            WHERE id = current_id;

            current_id := current_parent;
            depth := depth + 1;
        END LOOP;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # update_account_totals() : logique de calcul du total propre inchangée, on
    # ajoute juste la propagation du rollup vers les ancêtres après recalcul.
    op.execute("""
    CREATE OR REPLACE FUNCTION update_account_totals()
    RETURNS TRIGGER AS $$
    DECLARE
        affected_account_id UUID;
    BEGIN
        IF TG_OP = 'UPDATE' AND OLD.account_id IS DISTINCT FROM NEW.account_id THEN
            UPDATE accounts SET
                total_earned = COALESCE((
                    SELECT SUM(quantity) FROM splits
                    WHERE account_id = OLD.account_id AND quantity > 0
                ), 0),
                total_spent = COALESCE((
                    SELECT SUM(-quantity) FROM splits
                    WHERE account_id = OLD.account_id AND quantity < 0
                ), 0)
            WHERE id = OLD.account_id;
            PERFORM propagate_consolidated_totals(OLD.account_id);
        END IF;

        IF TG_OP = 'DELETE' THEN
            affected_account_id := OLD.account_id;
        ELSE
            affected_account_id := NEW.account_id;
        END IF;

        UPDATE accounts SET
            total_earned = COALESCE((
                SELECT SUM(quantity) FROM splits
                WHERE account_id = affected_account_id AND quantity > 0
            ), 0),
            total_spent = COALESCE((
                SELECT SUM(-quantity) FROM splits
                WHERE account_id = affected_account_id AND quantity < 0
            ), 0)
        WHERE id = affected_account_id;

        PERFORM propagate_consolidated_totals(affected_account_id);

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)

    # Sur (dé/re)parentage ou suppression d'un compte, recalcule l'ancienne ET la
    # nouvelle chaîne d'ancêtres.
    op.execute("""
    CREATE OR REPLACE FUNCTION handle_account_parent_change()
    RETURNS TRIGGER AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            PERFORM propagate_consolidated_totals(OLD.parent_id);
            RETURN OLD;
        END IF;

        IF TG_OP = 'UPDATE' AND OLD.parent_id IS DISTINCT FROM NEW.parent_id THEN
            PERFORM propagate_consolidated_totals(OLD.parent_id);
        END IF;

        UPDATE accounts SET
            consolidated_earned = total_earned + COALESCE((
                SELECT SUM(consolidated_earned) FROM accounts WHERE parent_id = NEW.id
            ), 0),
            consolidated_spent = total_spent + COALESCE((
                SELECT SUM(consolidated_spent) FROM accounts WHERE parent_id = NEW.id
            ), 0)
        WHERE id = NEW.id;

        PERFORM propagate_consolidated_totals(NEW.parent_id);
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_handle_account_parent_change
        AFTER INSERT OR UPDATE OF parent_id OR DELETE ON accounts
        FOR EACH ROW
        EXECUTE FUNCTION handle_account_parent_change();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_handle_account_parent_change ON accounts")
    op.execute("DROP FUNCTION IF EXISTS handle_account_parent_change()")

    # Restaure update_account_totals() à sa version d'origine (sans propagation).
    op.execute("""
    CREATE OR REPLACE FUNCTION update_account_totals()
    RETURNS TRIGGER AS $$
    DECLARE
        affected_account_id UUID;
    BEGIN
        IF TG_OP = 'UPDATE' AND OLD.account_id IS DISTINCT FROM NEW.account_id THEN
            UPDATE accounts SET
                total_earned = COALESCE((
                    SELECT SUM(quantity) FROM splits
                    WHERE account_id = OLD.account_id AND quantity > 0
                ), 0),
                total_spent = COALESCE((
                    SELECT SUM(-quantity) FROM splits
                    WHERE account_id = OLD.account_id AND quantity < 0
                ), 0)
            WHERE id = OLD.account_id;
        END IF;

        IF TG_OP = 'DELETE' THEN
            affected_account_id := OLD.account_id;
        ELSE
            affected_account_id := NEW.account_id;
        END IF;

        UPDATE accounts SET
            total_earned = COALESCE((
                SELECT SUM(quantity) FROM splits
                WHERE account_id = affected_account_id AND quantity > 0
            ), 0),
            total_spent = COALESCE((
                SELECT SUM(-quantity) FROM splits
                WHERE account_id = affected_account_id AND quantity < 0
            ), 0)
        WHERE id = affected_account_id;

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)

    op.execute("DROP FUNCTION IF EXISTS propagate_consolidated_totals(UUID)")
    op.drop_column('accounts', 'consolidated_spent')
    op.drop_column('accounts', 'consolidated_earned')
