from sqlalchemy import create_engine, event, DDL
from config import db_url
# import all models
from models.base import Base
from models.accounts import Accounts
from models.asset_possession import AssetPossession
from models.assets import Assets
from models.budget_accounts import BudgetAccounts
from models.budget_categories import BudgetCategories
from models.budget_tags import BudgetTags
from models.budgets import Budgets
from models.categories import Categories
from models.commodities import Commodities
from models.splits import Splits
from models.subscriptions import Subscriptions
from models.tags import Tags
from models.tags_on_split import TagsOnSplits
from models.transactions import Transactions
from models.users import Users

# import functions
from functions.check_category_id import check_category_id
from functions.update_budget_spent import update_budget_spent
from functions.update_timestamp import update_timestamp

# import triggers
from triggers.trg_check_category_id import trg_check_category_id
from triggers.trg_update_budget_spent import trg_update_budget_spent
from triggers.trg_update_timestamp_accounts import trg_update_timestamp_accounts
from triggers.trg_update_timestamp_budgets import trg_update_timestamp_budgets
from triggers.trg_update_timestamp_users import trg_update_timestamp_users

engine = create_engine(db_url, echo=True)


conn = engine.connect()
Base.metadata.drop_all(bind=conn)
conn.commit()
# Prepare the functions and triggers to be created at database Base.metadata.create_all(bind=conn)
# functions
event.listen(Base.metadata, 'before_create', check_category_id)
event.listen(Base.metadata, 'before_create', update_budget_spent)
event.listen(Base.metadata, 'before_create', update_timestamp)
# Triggers
event.listen(Transactions.metadata, 'after_create', trg_check_category_id)
event.listen(Splits.metadata, 'after_create', trg_update_budget_spent)
event.listen(Accounts.metadata, 'after_create', trg_update_timestamp_accounts)
event.listen(Budgets.metadata, 'after_create', trg_update_timestamp_budgets)
event.listen(Users.metadata, 'after_create', trg_update_timestamp_users)
# Create database structure
Base.metadata.create_all(bind=conn)
conn.commit()

