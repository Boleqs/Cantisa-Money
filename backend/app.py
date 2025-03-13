from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import FlaskConfig as flask_config
import hashlib

# Import tables models
from database.models.import_models import *

# import functions
from database.functions.import_functions import *
# TODO imports using * or name by name ?
# import triggers
from database.triggers.import_triggers import *

# Import routes
from routes.import_routes import *


app = Flask(__name__)
CORS(app)  # Ajout de cette ligne pour permettre les requêtes CORS
app.config.from_object(flask_config)
DB = SQLAlchemy(model_class=Base)
DB.init_app(app)
JWTManager(app)
# Routes declaration
UsersRoutes(app, DB, Users)
CommoditiesRoutes(app, DB, Users, Commodities)
AuthRoutes(app, DB, Users)



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
    user1_commodity2 = Commodities(user_id=user1_id, name='Dollar', short_name='USD', description='La monnaie américaine')
    user2_commodity = Commodities(user_id=user2_id, name='Euro', short_name='eu', description='La monnaie européenne')
    DB.session.add(user1_commodity)
    DB.session.add(user1_commodity2)
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
    #init_db()
    pass


if __name__ == '__main__':
    app.run(debug=True)


