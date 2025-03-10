from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import Config as flask_config
import hashlib

# Import tables
from database.models.base import Base
from database.models.accounts import Accounts
from database.models.asset_possession import AssetPossession
from database.models.assets import Assets
from database.models.budget_accounts import BudgetAccounts
from database.models.budget_categories import BudgetCategories
from database.models.budget_tags import BudgetTags
from database.models.budgets import Budgets
from database.models.categories import Categories
from database.models.commodities import Commodities
from database.models.splits import Splits
from database.models.subscriptions import Subscriptions
from database.models.tags import Tags
from database.models.tags_on_split import TagsOnSplits
from database.models.transactions import Transactions
from database.models.users import Users

# import functions
from database.functions.check_category_id import check_category_id
from database.functions.update_budget_spent import update_budget_spent
from database.functions.update_timestamp import update_timestamp

# import triggers
from database.triggers.trg_check_category_id import trg_check_category_id
from database.triggers.trg_update_budget_spent import trg_update_budget_spent
from database.triggers.trg_update_timestamp_accounts import trg_update_timestamp_accounts
from database.triggers.trg_update_timestamp_budgets import trg_update_timestamp_budgets
from database.triggers.trg_update_timestamp_users import trg_update_timestamp_users


app = Flask(__name__)
CORS(app)  # Ajout de cette ligne pour permettre les requêtes CORS
app.config.from_object(flask_config)
DB = SQLAlchemy(model_class=Base)
DB.init_app(app)


def init_db():
    # drop all for testing purpose
    DB.drop_all()
    DB.event.listen(Base.metadata, 'before_create', check_category_id)
    DB.event.listen(Base.metadata, 'before_create', update_budget_spent)
    DB.event.listen(Base.metadata, 'before_create', update_timestamp)
    # Triggers
    DB.event.listen(Transactions.metadata, 'after_create', trg_check_category_id)
    DB.event.listen(Splits.metadata, 'after_create', trg_update_budget_spent)
    DB.event.listen(Accounts.metadata, 'after_create', trg_update_timestamp_accounts)
    DB.event.listen(Budgets.metadata, 'after_create', trg_update_timestamp_budgets)
    DB.event.listen(Users.metadata, 'after_create', trg_update_timestamp_users)
    DB.create_all()

    # add data for testing purpose
    user1 = Users(username='user_1', email='user.1@example.com', password_hash=hashlib.sha256(bytes('password1', encoding="utf8")).hexdigest())
    user2 = Users(username='user_2', email='user.2@example.com', password_hash=hashlib.sha256(bytes('password2', encoding="utf8")).hexdigest())
    DB.session.add(user1)
    DB.session.add(user2)
    DB.session.commit()
    user1_id = DB.session.query(Users).filter(Users.username == 'user_1').first().id
    user2_id = DB.session.query(Users).filter(Users.username == 'user_2').first().id
    user1_commodity = Commodities(user_id=user1_id, name='Euro', short_name='eu', description='La monnaie européenne')
    user2_commodity = Commodities(user_id=user2_id, name='Euro', short_name='eu', description='La monnaie européenne')
    DB.session.add(user1_commodity)
    DB.session.add(user2_commodity)
    DB.session.commit()
    user1_commodity_id = DB.session.query(Commodities).filter(Commodities.user_id == user1_id).first().id
    user2_commodity_id = DB.session.query(Commodities).filter(Commodities.user_id == user2_id).first().id
    user1_account = Accounts(user_id=user1_id, name='user1_account', currency_id=user1_commodity_id, description='User 1 main account')
    user2_account = Accounts(user_id=user2_id, name='user2_account', currency_id=user2_commodity_id, description='User 2 main account', code='04356')
    DB.session.add(user1_account)
    DB.session.add(user2_account)
    DB.session.commit()

with app.app_context():
    init_db()


if __name__ == '__main__':
    app.run(debug=True)


