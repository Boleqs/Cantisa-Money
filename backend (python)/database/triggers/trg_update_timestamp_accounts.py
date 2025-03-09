from sqlalchemy import DDL


trg_update_timestamp_accounts = DDL("""
CREATE TRIGGER trg_update_timestamp_accounts
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();
""")