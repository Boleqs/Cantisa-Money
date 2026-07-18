"""budget spent currency conversion

Revision ID: 7f3b1a9d6c2e
Revises: 4a2c2d7a4f4b
Create Date: 2026-07-16 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7f3b1a9d6c2e'
down_revision: Union[str, Sequence[str], None] = '4a2c2d7a4f4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('budgets', sa.Column('amount_spent_incomplete', sa.Boolean(), nullable=False, server_default='false'))
    op.alter_column('budgets', 'amount_spent_incomplete', server_default=None)

    # Un budget scopé par catégorie/tag peut matcher des splits sur des comptes en devises
    # différentes — la somme brute des quantités n'a alors aucun sens. On convertit désormais
    # chaque split dans la devise affichée du propriétaire du budget (user_settings.currency,
    # repli EUR), via le taux le plus récent déjà en cache dans fx_rates (un trigger Postgres ne
    # peut pas appeler yfinance) ; si aucun taux n'est en cache pour une paire de devises
    # rencontrée, le split est exclu (SUM ignore les NULL) et amount_spent_incomplete passe à
    # true pour signaler que le total peut être sous-estimé, plutôt que de se taire.
    op.execute("""
    CREATE OR REPLACE FUNCTION update_budget_spent()
    RETURNS TRIGGER AS $$
    DECLARE
        affected_budget RECORD;
        target_currency VARCHAR;
        new_amount_spent NUMERIC;
        new_incomplete BOOLEAN;
        split_ref RECORD;
    BEGIN
        IF TG_OP = 'DELETE' THEN
            split_ref := OLD;
        ELSE
            split_ref := NEW;
        END IF;

        FOR affected_budget IN
            SELECT DISTINCT b.id, b.start_date, b.end_date, b.user_id
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
            SELECT COALESCE(us.currency, 'EUR') INTO target_currency
            FROM user_settings us WHERE us.user_id = affected_budget.user_id;
            IF target_currency IS NULL THEN
                target_currency := 'EUR';
            END IF;

            SELECT
                COALESCE(SUM(CASE
                    WHEN c.short_name = target_currency THEN -s.quantity
                    WHEN fx.rate IS NOT NULL THEN -s.quantity * fx.rate
                    ELSE NULL
                END), 0),
                COALESCE(bool_or(c.short_name <> target_currency AND fx.rate IS NULL), false)
            INTO new_amount_spent, new_incomplete
            FROM splits s
            JOIN transactions t ON t.id = s.tx_id
            JOIN accounts a ON a.id = s.account_id
            JOIN commodities c ON c.id = a.currency_id
            LEFT JOIN LATERAL (
                SELECT fr.rate FROM fx_rates fr
                WHERE fr.from_code = c.short_name AND fr.to_code = target_currency
                ORDER BY fr.rate_date DESC LIMIT 1
            ) fx ON c.short_name <> target_currency
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

            UPDATE budgets SET amount_spent = new_amount_spent, amount_spent_incomplete = new_incomplete
            WHERE id = affected_budget.id;
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
    op.drop_column('budgets', 'amount_spent_incomplete')
