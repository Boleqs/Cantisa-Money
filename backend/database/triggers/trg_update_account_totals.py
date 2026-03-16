from sqlalchemy import DDL

trg_update_account_totals = DDL("""
CREATE TRIGGER trg_update_account_totals
AFTER INSERT OR UPDATE OR DELETE ON splits
FOR EACH ROW
EXECUTE FUNCTION update_account_totals();
""")