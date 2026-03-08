from sqlalchemy import DDL

update_budget_spent = DDL("""
CREATE OR REPLACE FUNCTION update_budget_spent()
RETURNS TRIGGER AS $$
DECLARE
    affected_budget RECORD;
    new_amount_spent NUMERIC;
    split_ref RECORD;
BEGIN
    -- Utiliser OLD pour DELETE, NEW sinon
    IF TG_OP = 'DELETE' THEN
        split_ref := OLD;
    ELSE
        split_ref := NEW;
    END IF;

    -- Trouver tous les budgets potentiellement impactés par ce split :
    -- 1. Budgets liés au compte du split
    -- 2. Budgets liés à la catégorie de la transaction du split
    -- 3. Budgets liés à un tag posé sur ce split
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
        -- Recalculer amount_spent pour ce budget.
        -- Pour les budgets par compte  : on somme tous les splits (+ et -) du compte ciblé
        --   → permet de compter les remboursements.
        -- Pour les budgets par catégorie/tag : on exclut les comptes Expense/Income
        --   (contreparties comptables double-entrée) pour éviter les annulations.
        SELECT COALESCE(SUM(s.quantity), 0) INTO new_amount_spent
        FROM splits s
        JOIN transactions t ON t.id = s.tx_id
        JOIN accounts a ON a.id = s.account_id
        WHERE
            t.post_date BETWEEN affected_budget.start_date AND affected_budget.end_date
            AND (
                -- Budgets par compte : tous les splits du compte ciblé
                EXISTS (
                    SELECT 1 FROM budget_accounts ba
                    WHERE ba.budget_id = affected_budget.id AND ba.account_id = s.account_id
                )
                OR (
                    -- Budgets par catégorie : seulement les comptes réels (pas Expense/Income)
                    a.account_type NOT IN ('Expense', 'Income')
                    AND t.category_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM budget_categories bc
                        WHERE bc.budget_id = affected_budget.id AND bc.category_id = t.category_id
                    )
                )
                OR (
                    -- Budgets par tag : seulement les comptes réels (pas Expense/Income)
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