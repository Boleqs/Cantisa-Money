from sqlalchemy import DDL

update_budget_spent = DDL("""
CREATE OR REPLACE FUNCTION update_budget_spent()
RETURNS TRIGGER AS $$
DECLARE
    total_spent INT;
BEGIN
    -- Calculer le total des transactions liées aux comptes associés au budget
    SELECT COALESCE(SUM(s.quantity), 0) INTO total_spent
    FROM splits s
    WHERE s.account_id IN (
        -- SELECT account_id FROM budget_accounts WHERE budget_id = NEW.id
        SELECT account_id FROM budget_accounts WHERE budget_id = NEW.budget_id --ia
    );

    -- Ajouter les transactions liées aux catégories associées au budget
    SELECT COALESCE(total_spent + SUM(s.quantity), total_spent) INTO total_spent
    FROM splits s
    JOIN transactions t ON s.tx_id = t.id
    WHERE t.category_id IN (
        -- SELECT category_id FROM budget_categories WHERE budget_id = NEW.id
        SELECT category_id FROM budget_categories WHERE budget_id = NEW.budget_id --ia
    );

    -- Ajouter les transactions liées aux tags associés au budget
    SELECT COALESCE(total_spent + SUM(s.quantity), total_spent) INTO total_spent
    FROM splits s
    JOIN tags_on_split ts ON s.id = ts.split_id
    WHERE ts.tag_id IN (
        -- SELECT tag_id FROM budget_tags WHERE budget_id = NEW.id 
        SELECT tag_id FROM budget_tags WHERE budget_id = NEW.budget_id --ia
    );

    -- Mettre à jour le montant dépensé dans le budget
    UPDATE budgets
    SET amount_spent = total_spent
    -- WHERE id = NEW.id;
    WHERE id = NEW.budget_id; -- ia

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
