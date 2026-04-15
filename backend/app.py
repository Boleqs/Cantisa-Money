from dotenv import load_dotenv
load_dotenv()

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
UsersRoutes(app, DB, Users, UserRoles, Roles)
CommoditiesRoutes(app, DB, Users, Commodities)
AuthRoutes(app, DB, Users)
AccountsRoutes(app, DB, Users, Accounts)
TransactionsRoutes(app, DB, Transactions, Splits, TagsOnSplits)
BudgetsRoutes(app, DB, Budgets, BudgetAccounts, BudgetCategories, BudgetTags)
CategoriesRoutes(app, DB, Categories)
TagsRoutes(app, DB, Tags, TagsOnSplits, Splits, Transactions)
SubscriptionsRoutes(app, DB, Subscriptions)
DashboardRoutes(app, DB, Accounts, Transactions, Splits, Categories)
AssetsRoutes(app, DB, Assets, AssetPossession)
ReportsRoutes(app, DB, Accounts, Transactions, Splits, Categories)
RolesRoutes(app, DB, Users, Roles, Permissions, RolePermissions)
ImportRoutes(app, DB, Transactions, Splits)
AIRoutes(app, DB, Categories, Accounts)
TestRoutes(app, DB, Users, Accounts)


def reset_db():
    # drop all for testing purpose
    DB.drop_all()
    DB.event.listen(Base.metadata, 'before_create', check_category_id)
    DB.event.listen(Base.metadata, 'before_create', update_account_totals)
    DB.event.listen(Base.metadata, 'before_create', update_budget_spent)
    DB.event.listen(Base.metadata, 'before_create', update_timestamp)
    # Triggers
    DB.event.listen(Transactions.metadata, 'after_create', trg_check_category_id)
    DB.event.listen(Splits.metadata, 'after_create', trg_update_account_totals)
    DB.event.listen(Splits.metadata, 'after_create', trg_update_budget_spent)
    DB.event.listen(Accounts.metadata, 'after_create', trg_update_timestamp_accounts)
    DB.event.listen(Budgets.metadata, 'after_create', trg_update_timestamp_budgets)
    DB.event.listen(Users.metadata, 'after_create', trg_update_timestamp_users)
    DB.create_all()

def init_db():
    from datetime import date, datetime as dt

    # ── Utilisateurs ─────────────────────────────────────────────────────────
    loris = Users(username='Loris', email='loris@test.com',
                  password_hash=b'0x7ED3D060E511764096EF4A056021178758A8D32ECD1D2BA72B7E015AC9FFD13F',
                  salt=b'ee318ef8-cb0e-15c4-65c5-d1d7d26ae0d1')
    alice = Users(username='Alice', email='alice@test.com',
                  password_hash=b'0x7ED3D060E511764096EF4A056021178758A8D32ECD1D2BA72B7E015AC9FFD13F',
                  salt=b'ee318ef8-cb0e-15c4-65c5-d1d7d26ae0d1')
    DB.session.add_all([loris, alice])
    DB.session.flush()

    # Loris = admin, Alice = standard user
    DB.session.add(UserRoles(user_id=loris.id, role_id=uuid.UUID('00000000-cafe-4bca-82bb-a0cec8e5a6ba')))
    DB.session.add(UserRoles(user_id=alice.id, role_id=uuid.UUID('00000000-cafe-46fe-9a04-a03b4c253f1f')))
    DB.session.commit()

    # ── Devises ───────────────────────────────────────────────────────────────
    eur = Commodities(user_id=loris.id, name='Euro', short_name='EUR', description='Monnaie européenne')
    usd = Commodities(user_id=loris.id, name='Dollar', short_name='USD', description='Monnaie américaine')
    DB.session.add_all([eur, usd])
    DB.session.flush()

    # ── Comptes ───────────────────────────────────────────────────────────────
    acc_courant = Accounts(user_id=loris.id, name='Compte Courant BNP', currency_id=eur.id,
                           account_type='Current', description='Compte bancaire principal')
    acc_livret  = Accounts(user_id=loris.id, name='Livret A', currency_id=eur.id,
                           account_type='Assets', description='Épargne réglementée')
    acc_invest  = Accounts(user_id=loris.id, name='Compte Titres', currency_id=usd.id,
                           account_type='Assets', description='Portefeuille boursier')
    acc_salaire = Accounts(user_id=loris.id, name='Salaires', currency_id=eur.id,
                           account_type='Income', description='Source revenus')
    acc_depenses = Accounts(user_id=loris.id, name='Dépenses courantes', currency_id=eur.id,
                            account_type='Expense', description='Dépenses quotidiennes')
    DB.session.add_all([acc_courant, acc_livret, acc_invest, acc_salaire, acc_depenses])
    DB.session.flush()

    # ── Catégories ────────────────────────────────────────────────────────────
    cat_alim      = Categories(user_id=loris.id, name='Alimentation',  description='Courses, restaurants')
    cat_transport = Categories(user_id=loris.id, name='Transport',     description='Essence, transports en commun')
    cat_loisirs   = Categories(user_id=loris.id, name='Loisirs',       description='Sorties, voyages, abonnements')
    cat_sante     = Categories(user_id=loris.id, name='Santé',         description='Médecins, pharmacie')
    cat_logement  = Categories(user_id=loris.id, name='Logement',      description='Loyer, charges')
    DB.session.add_all([cat_alim, cat_transport, cat_loisirs, cat_sante, cat_logement])
    DB.session.flush()

    # ── Tags ──────────────────────────────────────────────────────────────────
    tag_recurrent = Tags(user_id=loris.id, name='récurrent',     color='blue')
    tag_urgent    = Tags(user_id=loris.id, name='urgent',        color='red')
    tag_pro       = Tags(user_id=loris.id, name='professionnel', color='purple')
    tag_perso     = Tags(user_id=loris.id, name='personnel',     color='green')
    DB.session.add_all([tag_recurrent, tag_urgent, tag_pro, tag_perso])
    DB.session.flush()

    # ── Budgets ───────────────────────────────────────────────────────────────
    # Créés AVANT les transactions pour que le trigger les trouve au moment de l'insertion des splits
    budget_alim    = Budgets(user_id=loris.id, name='Alimentation mars',
                             amount_allocated=400,
                             start_date=dt(2026, 3, 1), end_date=dt(2026, 3, 31))
    budget_loisirs = Budgets(user_id=loris.id, name='Loisirs mars',
                             amount_allocated=150,
                             start_date=dt(2026, 3, 1), end_date=dt(2026, 3, 31))
    budget_global  = Budgets(user_id=loris.id, name='Budget global compte courant',
                             amount_allocated=2000,
                             start_date=dt(2026, 3, 1), end_date=dt(2026, 3, 31))
    budget_recur   = Budgets(user_id=loris.id, name='Dépenses récurrentes',
                             amount_allocated=500,
                             start_date=dt(2026, 3, 1), end_date=dt(2026, 3, 31))
    DB.session.add_all([budget_alim, budget_loisirs, budget_global, budget_recur])
    DB.session.flush()

    DB.session.add(BudgetCategories(budget_id=budget_alim.id,    category_id=cat_alim.id))
    DB.session.add(BudgetCategories(budget_id=budget_loisirs.id, category_id=cat_loisirs.id))
    DB.session.add(BudgetAccounts(budget_id=budget_global.id,    account_id=acc_courant.id))
    DB.session.add(BudgetTags(budget_id=budget_recur.id,         tag_id=tag_recurrent.id))
    DB.session.commit()

    # ── Transactions & Splits ─────────────────────────────────────────────────
    def make_tx(desc, d, cat=None, splits_data=None, tags_on=None):
        """Crée une transaction + splits. tags_on = [(split_index, tag), ...]"""
        t = Transactions(user_id=loris.id, currency_id=eur.id,
                         post_date=d, effective_date=d,
                         description=desc, category_id=cat, is_cleared=True)
        DB.session.add(t)
        DB.session.flush()
        created_splits = []
        for acc_id, qty in splits_data:
            s = Splits(tx_id=t.id, account_id=acc_id, quantity=qty)
            DB.session.add(s)
            DB.session.flush()
            created_splits.append(s)
        if tags_on:
            for split_idx, tag in tags_on:
                DB.session.add(TagsOnSplits(split_id=created_splits[split_idx].id, tag_id=tag.id))
        return t

    # Janvier 2026
    make_tx('Salaire janvier',       date(2026, 1, 5),  splits_data=[(acc_courant.id, 3200),  (acc_salaire.id, -3200)], tags_on=[(0, tag_recurrent)])
    make_tx('Loyer janvier',         date(2026, 1, 6),  cat_logement.id,  [(acc_courant.id, -950),  (acc_depenses.id, 950)],  [(0, tag_recurrent)])
    make_tx('Courses Carrefour',     date(2026, 1, 8),  cat_alim.id,      [(acc_courant.id, -87),   (acc_depenses.id, 87)],   [(0, tag_perso)])
    make_tx('Abonnement Netflix',    date(2026, 1, 10), cat_loisirs.id,   [(acc_courant.id, -15),   (acc_depenses.id, 15)],   [(0, tag_recurrent)])
    make_tx('Essence',               date(2026, 1, 14), cat_transport.id, [(acc_courant.id, -65),   (acc_depenses.id, 65)],   [(0, tag_perso)])
    make_tx('Pharmacie',             date(2026, 1, 17), cat_sante.id,     [(acc_courant.id, -23),   (acc_depenses.id, 23)],   [(0, tag_urgent)])
    make_tx('Virement Livret A',     date(2026, 1, 20), splits_data=[(acc_courant.id, -500),  (acc_livret.id, 500)])
    make_tx('Restaurant Chez Paul',  date(2026, 1, 22), cat_loisirs.id,   [(acc_courant.id, -45),   (acc_depenses.id, 45)],   [(0, tag_perso)])
    make_tx('Courses Bio Market',    date(2026, 1, 25), cat_alim.id,      [(acc_courant.id, -112),  (acc_depenses.id, 112)])
    make_tx('Abonnement Spotify',    date(2026, 1, 28), cat_loisirs.id,   [(acc_courant.id, -10),   (acc_depenses.id, 10)],   [(0, tag_recurrent)])

    # Février 2026
    make_tx('Salaire février',       date(2026, 2, 5),  splits_data=[(acc_courant.id, 3200),  (acc_salaire.id, -3200)], tags_on=[(0, tag_recurrent)])
    make_tx('Loyer février',         date(2026, 2, 6),  cat_logement.id,  [(acc_courant.id, -950),  (acc_depenses.id, 950)],  [(0, tag_recurrent)])
    make_tx('Courses Leclerc',       date(2026, 2, 9),  cat_alim.id,      [(acc_courant.id, -95),   (acc_depenses.id, 95)],   [(0, tag_perso)])
    make_tx('Billet train Paris',    date(2026, 2, 12), cat_transport.id, [(acc_courant.id, -72),   (acc_depenses.id, 72)],   [(0, tag_pro)])
    make_tx('Cinéma',                date(2026, 2, 14), cat_loisirs.id,   [(acc_courant.id, -22),   (acc_depenses.id, 22)],   [(0, tag_perso)])
    make_tx('Abonnement Netflix',    date(2026, 2, 10), cat_loisirs.id,   [(acc_courant.id, -15),   (acc_depenses.id, 15)],   [(0, tag_recurrent)])
    make_tx('Médecin généraliste',   date(2026, 2, 16), cat_sante.id,     [(acc_courant.id, -30),   (acc_depenses.id, 30)],   [(0, tag_urgent)])
    make_tx('Virement Livret A',     date(2026, 2, 18), splits_data=[(acc_courant.id, -300),  (acc_livret.id, 300)])
    make_tx('Courses Monoprix',      date(2026, 2, 22), cat_alim.id,      [(acc_courant.id, -68),   (acc_depenses.id, 68)],   [(0, tag_perso)])
    make_tx('Abonnement Spotify',    date(2026, 2, 28), cat_loisirs.id,   [(acc_courant.id, -10),   (acc_depenses.id, 10)],   [(0, tag_recurrent)])

    # Mars 2026 (mois en cours)
    make_tx('Salaire mars',          date(2026, 3, 5),  splits_data=[(acc_courant.id, 3200),  (acc_salaire.id, -3200)], tags_on=[(0, tag_recurrent)])
    make_tx('Loyer mars',            date(2026, 3, 6),  cat_logement.id,  [(acc_courant.id, -950),  (acc_depenses.id, 950)],  [(0, tag_recurrent)])
    make_tx('Courses Aldi',          date(2026, 3, 7),  cat_alim.id,      [(acc_courant.id, -54),   (acc_depenses.id, 54)],   [(0, tag_perso)])
    make_tx('Abonnement Netflix',    date(2026, 3, 8),  cat_loisirs.id,   [(acc_courant.id, -15),   (acc_depenses.id, 15)],   [(0, tag_recurrent)])
    DB.session.commit()

    # ── Abonnements ───────────────────────────────────────────────────────────
    DB.session.add_all([
        Subscriptions(user_id=loris.id, name='Netflix',  recurrence=30, amount=15,
                      from_account_id=acc_courant.id, to_account_id=acc_depenses.id, category_id=cat_loisirs.id),
        Subscriptions(user_id=loris.id, name='Spotify',  recurrence=30, amount=10,
                      from_account_id=acc_courant.id, to_account_id=acc_depenses.id, category_id=cat_loisirs.id),
        Subscriptions(user_id=loris.id, name='Loyer',    recurrence=30, amount=950,
                      from_account_id=acc_courant.id, to_account_id=acc_depenses.id, category_id=cat_logement.id),
        Subscriptions(user_id=loris.id, name='Mutuelle', recurrence=30, amount=55,
                      from_account_id=acc_courant.id, to_account_id=acc_depenses.id, category_id=cat_sante.id),
    ])
    DB.session.commit()

    # ── Actifs (Portfolio) ────────────────────────────────────────────────────
    asset_apple = Assets(user_id=loris.id, symbol='AAPL', name='Apple Inc.',
                         asset_type='Stock', sector='Technology',
                         commodity_id=usd.id, value_per_unit=185)
    asset_etf   = Assets(user_id=loris.id, symbol='SPY',  name='S&P 500 ETF',
                         asset_type='ETF', sector='Diversified',
                         commodity_id=usd.id, value_per_unit=520)
    asset_immo  = Assets(user_id=loris.id, symbol='APT01', name='Studio Paris 11e',
                         asset_type='RealEstate',
                         commodity_id=eur.id, value_per_unit=220000)
    DB.session.add_all([asset_apple, asset_etf, asset_immo])
    DB.session.flush()

    DB.session.add_all([
        AssetPossession(user_id=loris.id, asset_id=asset_apple.id, account_id=acc_invest.id, quantity=15),
        AssetPossession(user_id=loris.id, asset_id=asset_etf.id,   account_id=acc_invest.id, quantity=8),
        AssetPossession(user_id=loris.id, asset_id=asset_immo.id,  account_id=acc_invest.id, quantity=1),
    ])
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


