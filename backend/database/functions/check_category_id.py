from sqlalchemy import DDL
# % must be escaped with %% as per
# https://docs.sqlalchemy.org/en/20/core/ddl.html#sqlalchemy.schema.DDL.params.statement
check_category_id = DDL("""
CREATE OR REPLACE FUNCTION check_category_id()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM categories WHERE id = NEW.category_id AND user_id = NEW.user_id) THEN
        RAISE EXCEPTION 'Invalid category_id %% for user_id %%', NEW.category_id, NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
