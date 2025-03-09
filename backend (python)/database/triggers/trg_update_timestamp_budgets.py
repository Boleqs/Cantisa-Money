from sqlalchemy import DDL

trg_update_timestamp_budgets = DDL("""
CREATE TRIGGER trg_update_timestamp_budgets
BEFORE UPDATE ON budgets
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();
""")