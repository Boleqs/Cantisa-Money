from sqlalchemy import DDL

trg_update_timestamp_users = DDL("""
CREATE TRIGGER trg_update_timestamp_users
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();
""")