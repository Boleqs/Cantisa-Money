from sqlalchemy import DDL

trg_update_budget_spent = DDL("""
CREATE TRIGGER trg_update_budget_spent
AFTER INSERT OR UPDATE OR DELETE ON splits
FOR EACH ROW
EXECUTE FUNCTION update_budget_spent();
""")