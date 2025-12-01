from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from config import FlaskConfig as flask_config, VAR_PERMISSIONS_LIST
import uuid


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
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "http://localhost:5173"}})  # Ajout de cette ligne pour permettre les requêtes CORS
app.config.from_object(flask_config)
DB = SQLAlchemy(model_class=Base)
DB.init_app(app)
JWTManager(app)
# Routes declaration
UsersRoutes(app, DB, Users, UserRoles)
CommoditiesRoutes(app, DB, Users, Commodities)
AuthRoutes(app, DB, Users)

def reset_db():
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

def init_db():
    # add data for testing purpose
    user1 = Users(username='Loris',
                  email='loris@test.com',
                  password_hash=b'0x7ED3D060E511764096EF4A056021178758A8D32ECD1D2BA72B7E015AC9FFD13F',
                  salt=b'ee318ef8-cb0e-15c4-65c5-d1d7d26ae0d1')
    DB.session.add(user1)
    DB.session.commit()
    user1_id = DB.session.query(Users).filter(Users.username == 'Loris').first().id
    user_role = UserRoles(user_id=user1_id,
                          role_id='00000000-cafe-46fe-9a04-a03b4c253f1f')
    DB.session.add(user_role)
    DB.session.commit()
    user1_commodity = Commodities(user_id=user1_id, name='Euro', short_name='eu', description='La monnaie européenne')
    user1_commodity2 = Commodities(user_id=user1_id, name='Dollar', short_name='USD', description='La monnaie américaine')
    DB.session.add(user1_commodity)
    DB.session.add(user1_commodity2)
    DB.session.commit()
    user1_commodity_id = DB.session.query(Commodities).filter(Commodities.user_id == user1_id).first().id
    user1_commodity_id2 = DB.session.query(Commodities).filter(Commodities.user_id == user1_id and Commodities.name == 'Dollar').first().id

    user1_account = Accounts(user_id=user1_id, name='Compte courant', currency_id=user1_commodity_id,
                             description='Loris main account')
    user1_account2 = Accounts(user_id=user1_id, name='Compte Investissment', currency_id=user1_commodity_id2,
                             description='Loris second account')
    DB.session.add(user1_account)
    DB.session.add(user1_account2)
    DB.session.commit()


def insert_permissions():
    for VAR_PERMISSION in VAR_PERMISSIONS_LIST:
        DB.session.add(Permissions(id=VAR_PERMISSIONS_LIST[VAR_PERMISSION]['id'],
                                   name=VAR_PERMISSION,
                                   description=VAR_PERMISSIONS_LIST[VAR_PERMISSION]['description']))
    DB.session.commit()


def insert_roles():
    roles = [
        Roles(id=uuid.UUID("00000000-cafe-4bca-82bb-a0cec8e5a6ba"), name="Global administrator", description="Default admin role with all rights"),
        Roles(id=uuid.UUID("00000000-cafe-46fe-9a04-a03b4c253f1f"), name="Standard user", description="Default user role with only rights on its own data")
    ]
    for role in roles:
        DB.session.add(role)
    DB.session.commit()


def assign_permissions_to_roles():
    role_permissions = {
        Roles.query.filter(Roles.name == "Global administrator").first().id:
            Permissions.query.filter(Permissions.name == "Delete users").first().id,

    }
    for role_id in role_permissions.keys():
        DB.session.add(RolePermissions(role_id=role_id, permission_id=role_permissions[role_id]))
    DB.session.commit()

with app.app_context():
    reset_db()
    insert_permissions()
    insert_roles()
    assign_permissions_to_roles()
    init_db()
    pass

uuid.uuid4()
if __name__ == '__main__':
    app.run(debug=True)


