from sqlalchemy import DDL

update_account_totals = DDL("""
CREATE OR REPLACE FUNCTION update_account_totals()
RETURNS TRIGGER AS $$
DECLARE
    affected_account_id UUID;
BEGIN
    -- Pour UPDATE, si le compte source a changé on recalcule aussi l'ancien
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

    -- Déterminer le compte à recalculer
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