from sqlalchemy import DDL

trg_check_category_id = DDL("""
CREATE TRIGGER trg_check_category_id
BEFORE INSERT OR UPDATE ON transactions
FOR EACH ROW
EXECUTE FUNCTION check_category_id();
""")