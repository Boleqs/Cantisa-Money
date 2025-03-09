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
    data_list = [user1, user2]
    for data in data_list:
        DB.session.add(data)
    DB.session.commit()
    user1_id = DB.session.query(Users).filter(Users.username == 'user_1').first().id
    print(user1_id)


with app.app_context():
    init_db()




@app.route('/api/virements', methods=['GET'])
def get_virements():
    virements = Virement.query.all()
    return jsonify([{'id': virement.id, 'type': virement.type, 'date_prod': virement.date_prod, 'montant': virement.montant, 'description': virement.description} for virement in virements])

@app.route('/api/virements/<id>', methods=['DELETE'])
def delete_virement(id):
    virement = Virement.query.get(id)
    if virement:
        db.session.delete(virement)
        db.session.commit()
        return jsonify({'message': 'Virement deteted successfully'}), 200
    else:
        return jsonify({'message': 'Virement not found'}), 404

@app.route('/api/virements/<id>', methods=['PUT'])
def modify_virement(id):
    virement = Virement.query.get(id)
    if virement:
        id = request.json.get('id', virement.id)
        virement.id = id
        type = request.json.get('type', virement.type)
        virement.type = type
        date_prod = request.json.get('date_prod', virement.date_prod)
        virement.date_prod = date_prod
        montant = request.json.get('montant', virement.montant)
        virement.montant = montant
        description = request.json.get('description', virement.description)
        virement.description = description
        db.session.commit()
        return jsonify({'message': 'Virement modified successfully'}), 200
    else:
        return jsonify({'message': 'Virement not found'}), 404

@app.route('/api/virements', methods=['POST'])
def add_virement():
    type = request.json.get('type')
    date_prod = request.json.get('date_prod')
    montant = request.json.get('montant')
    description = request.json.get('description')
    virement = Virement(type=type, date_prod=date_prod, montant=montant, description=description)
    db.session.add(virement)
    db.session.commit()
    return jsonify({
        'id': virement.id,
        'type': virement.type,
        'date_prod': virement.date_prod,
        'montant': virement.montant,
        'description': virement.description
    }), 201


if __name__ == '__main__':
    app.run(debug=True)


