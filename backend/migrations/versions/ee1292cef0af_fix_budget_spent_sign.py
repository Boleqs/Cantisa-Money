"""fix budget spent sign

Revision ID: ee1292cef0af
Revises: 9a1d4e6c2b3f
Create Date: 2026-07-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ee1292cef0af'
down_revision: Union[str, Sequence[str], None] = '9a1d4e6c2b3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # amount_spent doit être positif pour une dépense (même convention que total_spent des
    # comptes, qui fait SUM(-quantity) WHERE quantity < 0) — la somme brute des splits laissait
    # amount_spent négatif pour les budgets par catégorie/tag (une dépense y est une quantité
    # négative côté compte réel, le côté Expense étant exclu pour ne pas la compter deux fois).
    op.execute("""
    CREATE OR REPLACE FUNCTION update_budget_spent()
    RETURNS TRIGGER AS $$
    DECLARE
        affected_budget RECORD;
        new_amount_spent NUMERIC;
        split_ref RECORD;
    BEGIN
        IF TG_OP = 'DELETE' THEN
            split_ref := OLD;
        ELSE
            split_ref := NEW;
        END IF;

        FOR affected_budget IN
            SELECT DISTINCT b.id, b.start_date, b.end_date
            FROM budgets b
            WHERE
                EXISTS (
                    SELECT 1 FROM budget_accounts ba
                    WHERE ba.budget_id = b.id AND ba.account_id = split_ref.account_id
                )
                OR EXISTS (
                    SELECT 1 FROM budget_categories bc
                    JOIN transactions t ON t.id = split_ref.tx_id
                    WHERE bc.budget_id = b.id
                      AND bc.category_id = t.category_id
                      AND t.category_id IS NOT NULL
                )
                OR EXISTS (
                    SELECT 1 FROM budget_tags bt
                    JOIN tags_on_split tos ON tos.tag_id = bt.tag_id
                    WHERE bt.budget_id = b.id AND tos.split_id = split_ref.id
                )
        LOOP
            SELECT COALESCE(-SUM(s.quantity), 0) INTO new_amount_spent
            FROM splits s
            JOIN transactions t ON t.id = s.tx_id
            JOIN accounts a ON a.id = s.account_id
            WHERE
                t.post_date BETWEEN affected_budget.start_date AND affected_budget.end_date
                AND (
                    EXISTS (
                        SELECT 1 FROM budget_accounts ba
                        WHERE ba.budget_id = affected_budget.id AND ba.account_id = s.account_id
                    )
                    OR (
                        a.account_type NOT IN ('Expense', 'Income')
                        AND t.category_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM budget_categories bc
                            WHERE bc.budget_id = affected_budget.id AND bc.category_id = t.category_id
                        )
                    )
                    OR (
                        a.account_type NOT IN ('Expense', 'Income')
                        AND EXISTS (
                            SELECT 1 FROM tags_on_split tos
                            JOIN budget_tags bt ON bt.tag_id = tos.tag_id
                            WHERE tos.split_id = s.id AND bt.budget_id = affected_budget.id
                        )
                    )
                );

            UPDATE budgets SET amount_spent = new_amount_spent WHERE id = affected_budget.id;
        END LOOP;

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
    CREATE OR REPLACE FUNCTION update_budget_spent()
    RETURNS TRIGGER AS $$
    DECLARE
        affected_budget RECORD;
        new_amount_spent NUMERIC;
        split_ref RECORD;
    BEGIN
        IF TG_OP = 'DELETE' THEN
            split_ref := OLD;
        ELSE
            split_ref := NEW;
        END IF;

        FOR affected_budget IN
            SELECT DISTINCT b.id, b.start_date, b.end_date
            FROM budgets b
            WHERE
                EXISTS (
                    SELECT 1 FROM budget_accounts ba
                    WHERE ba.budget_id = b.id AND ba.account_id = split_ref.account_id
                )
                OR EXISTS (
                    SELECT 1 FROM budget_categories bc
                    JOIN transactions t ON t.id = split_ref.tx_id
                    WHERE bc.budget_id = b.id
                      AND bc.category_id = t.category_id
                      AND t.category_id IS NOT NULL
                )
                OR EXISTS (
                    SELECT 1 FROM budget_tags bt
                    JOIN tags_on_split tos ON tos.tag_id = bt.tag_id
                    WHERE bt.budget_id = b.id AND tos.split_id = split_ref.id
                )
        LOOP
            SELECT COALESCE(SUM(s.quantity), 0) INTO new_amount_spent
            FROM splits s
            JOIN transactions t ON t.id = s.tx_id
            JOIN accounts a ON a.id = s.account_id
            WHERE
                t.post_date BETWEEN affected_budget.start_date AND affected_budget.end_date
                AND (
                    EXISTS (
                        SELECT 1 FROM budget_accounts ba
                        WHERE ba.budget_id = affected_budget.id AND ba.account_id = s.account_id
                    )
                    OR (
                        a.account_type NOT IN ('Expense', 'Income')
                        AND t.category_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM budget_categories bc
                            WHERE bc.budget_id = affected_budget.id AND bc.category_id = t.category_id
                        )
                    )
                    OR (
                        a.account_type NOT IN ('Expense', 'Income')
                        AND EXISTS (
                            SELECT 1 FROM tags_on_split tos
                            JOIN budget_tags bt ON bt.tag_id = tos.tag_id
                            WHERE tos.split_id = s.id AND bt.budget_id = affected_budget.id
                        )
                    )
                );

            UPDATE budgets SET amount_spent = new_amount_spent WHERE id = affected_budget.id;
        END LOOP;

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END;
    $$ LANGUAGE plpgsql;
    """)
