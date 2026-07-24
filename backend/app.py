from dotenv import load_dotenv
load_dotenv()

import os
import sys
# Certains modules (routes/*, utils/wealth.py, database/models/users.py...) importent via
# `from backend.xxx import yyy`, ce qui suppose la racine du repo sur sys.path (PyCharm l'ajoute
# automatiquement via sa config de run, pas un `python app.py` lancé en terminal nu depuis backend/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

from config import FlaskConfig as flask_config, VAR_PERMISSIONS_LIST, VAR_STANDARD_USER_ROLE_ID, HttpCode
from utils.api_responses import json_response
from utils.logs import log
import uuid


# Import tables models
from database.models.import_models import *

# Import routes
from routes.import_routes import *


app = Flask(__name__)
# Une ou plusieurs origines séparées par des virgules (ex: "https://app.example.com,https://autre.com")
CORS_ORIGINS = [o.strip() for o in os.environ.get('CORS_ORIGINS', 'http://localhost:5173').split(',') if o.strip()]
CORS(app, supports_credentials=True, resources={r"/*": {"origins": CORS_ORIGINS}})
app.config.from_object(flask_config)
DB = SQLAlchemy(model_class=Base)
DB.init_app(app)
JWTManager(app)
limiter = Limiter(get_remote_address, app=app, storage_uri="memory://")
# Routes declaration
UsersRoutes(app, DB, Users, UserRoles, Roles, Permissions, RolePermissions)
CommoditiesRoutes(app, DB, Users, Commodities, FxRates, UserSettings, Accounts, Transactions, Assets)
AuthRoutes(app, DB, Users, UserRoles, limiter)
AccountsRoutes(app, DB, Users, Accounts)
TransactionsRoutes(app, DB, Transactions, Splits, TagsOnSplits, Users, Accounts, Categories, Commodities, FxRates)
BudgetsRoutes(app, DB, Budgets, BudgetAccounts, BudgetCategories, BudgetTags, Users, FxRates, Commodities, UserSettings)
CategoriesRoutes(app, DB, Categories, Users)
TagsRoutes(app, DB, Tags, TagsOnSplits, Splits, Transactions, Users)
SubscriptionsRoutes(app, DB, Subscriptions, Users, Transactions, Splits, Accounts)
DashboardRoutes(app, DB, Accounts, Transactions, Splits, Categories, Users, Commodities, FxRates, UserSettings)
AssetsRoutes(app, DB, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Accounts, Transactions, Splits, WealthSnapshot, Users, AssetValuations, UserSettings)
ReportsRoutes(app, DB, Accounts, Transactions, Splits, Categories, Users, Budgets, Subscriptions, Tags, TagsOnSplits, Commodities, FxRates, UserSettings)
RolesRoutes(app, DB, Users, Roles, Permissions, RolePermissions)
ImportRoutes(app, DB, Transactions, Splits, Users, Categories)
DocumentsRoutes(app, DB, TransactionDocuments, Transactions, Splits, TagsOnSplits, Tags, Accounts, Users)
AIRoutes(app, DB, Categories, Accounts, Users)
ReconcileRoutes(app, DB, Transactions, Splits, Accounts, Users)
TestRoutes(app, DB, Users, Accounts)
MarketsRoutes(app, Users, DB, Watchlist, MarketIndex)
WealthRoutes(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, WealthSnapshot, Users)
LoansRoutes(app, DB, Loans, LoanInstallments, LoanRateRevisions, Users, Transactions, Splits, Accounts, Commodities)
SettingsRoutes(app, DB, UserSettings, Users, Commodities, Budgets, FxRates)
OnboardingRoutes(app, DB, UserSettings, Commodities, Accounts, Categories)
TaxRoutes(app, DB, Users, TaxRegime, TaxHouseholdProfile, TaxHouseholdIncome, Categories,
          Transactions, Splits, Accounts, Commodities, FxRates, UserSettings,
          AssetDisposal, AssetPossession, Assets)
BackupRoutes(app, DB, Users, Commodities, Accounts, Categories, Tags, Budgets, BudgetAccounts,
             BudgetCategories, BudgetTags, Subscriptions, Assets, AssetPossession, AssetDisposal,
             AssetValuations, Transactions, Splits, TagsOnSplits, UserSettings, TransactionDocuments)
CustomReportsRoutes(app, DB, Users, CustomReports, Splits, Transactions, Accounts, Categories,
                     Tags, TagsOnSplits, Commodities, FxRates, UserSettings)


@app.errorhandler(HTTPException)
def handle_http_exception(e):
    # Laisse passer les erreurs HTTP volontaires (404, 403, etc.) mais en JSON plutôt que la page
    # HTML par défaut de Flask, pour rester cohérent avec le reste de l'API.
    return json_response(e.description, e.code)


@app.errorhandler(Exception)
def handle_unexpected_exception(e):
    # Filet de sécurité : une exception non gérée ne doit ni faire fuiter une trace Python au
    # client, ni renvoyer une page HTML — toujours du JSON, avec le détail dans les logs serveur.
    log(f"Erreur non gérée : {e}", filename='app')
    return json_response('Erreur interne du serveur', HttpCode.SERVER_ERROR)


def _alembic_config():
    from alembic.config import Config
    cfg = Config(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alembic.ini'))
    cfg.set_main_option('sqlalchemy.url', app.config['SQLALCHEMY_DATABASE_URI'])
    return cfg


def create_tables():
    """Applique les migrations Alembic jusqu'à la dernière — idempotent, ne touche à rien si le
    schéma est déjà à jour (remplace l'ancien DB.create_all() + triggers enregistrés à la main)."""
    from alembic import command
    command.upgrade(_alembic_config(), 'head')


def reset_db():
    """Supprime tout (y compris le suivi des migrations Alembic) et réapplique les migrations
    depuis zéro — perte de données. N'est appelé que si RESET_DB_ON_START=true."""
    from alembic import command
    from sqlalchemy import text
    DB.session.execute(text('DROP SCHEMA public CASCADE'))
    DB.session.execute(text('CREATE SCHEMA public'))
    DB.session.commit()
    command.upgrade(_alembic_config(), 'head')

def init_db():
    from datetime import date, datetime as dt

    # ── Utilisateurs ─────────────────────────────────────────────────────────
    # Mot de passe de démo identique pour les deux comptes de seed — voir README.
    DEMO_PASSWORD = 'CantisaDemo2026!'
    loris = Users(username='Loris', email='loris@test.com', password_hash=b'', salt=b'')
    loris.set_password(DEMO_PASSWORD)
    alice = Users(username='Alice', email='alice@test.com', password_hash=b'', salt=b'')
    alice.set_password(DEMO_PASSWORD)
    DB.session.add_all([loris, alice])
    DB.session.flush()

    # Loris = admin, Alice = standard user
    DB.session.add(UserRoles(user_id=loris.id, role_id=uuid.UUID('00000000-cafe-4bca-82bb-a0cec8e5a6ba')))
    DB.session.add(UserRoles(user_id=alice.id, role_id=VAR_STANDARD_USER_ROLE_ID))
    # Comptes de démo déjà entièrement configurés : onboarding_completed=True pour ne pas les
    # faire passer par l'assistant de premier login (voir rt_onboarding.py).
    DB.session.add(UserSettings(user_id=loris.id, currency='EUR', onboarding_completed=True))
    DB.session.add(UserSettings(user_id=alice.id, currency='EUR', onboarding_completed=True))
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
        Subscriptions(user_id=loris.id, name='Netflix',  schedule_type='monthly', day_of_month=8, amount=15,
                      from_account_id=acc_courant.id, to_account_id=acc_depenses.id, category_id=cat_loisirs.id),
        Subscriptions(user_id=loris.id, name='Spotify',  schedule_type='monthly', day_of_month=28, amount=10,
                      from_account_id=acc_courant.id, to_account_id=acc_depenses.id, category_id=cat_loisirs.id),
        Subscriptions(user_id=loris.id, name='Loyer',    schedule_type='monthly', day_of_month=6, amount=950,
                      from_account_id=acc_courant.id, to_account_id=acc_depenses.id, category_id=cat_logement.id),
        Subscriptions(user_id=loris.id, name='Mutuelle', schedule_type='monthly', day_of_month=1, amount=55,
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

    # purchase_date renseignée : sans elle, backfill_wealth_history() (utilisé par la page
    # Patrimoine et le rapport correspondant) n'a aucune date de départ et n'installe qu'un seul
    # point d'historique (celui du jour), ce qui casse les graphiques d'évolution.
    DB.session.add_all([
        AssetPossession(user_id=loris.id, asset_id=asset_apple.id, account_id=acc_invest.id, quantity=15,
                        purchase_date=dt(2026, 1, 10), purchase_price=150, purchase_price_native=150),
        AssetPossession(user_id=loris.id, asset_id=asset_etf.id,   account_id=acc_invest.id, quantity=8,
                        purchase_date=dt(2026, 1, 15), purchase_price=480, purchase_price_native=480),
        AssetPossession(user_id=loris.id, asset_id=asset_immo.id,  account_id=acc_invest.id, quantity=1,
                        purchase_date=dt(2026, 2, 1), purchase_price=200000, purchase_price_native=200000),
    ])
    DB.session.commit()


def create_first_admin():
    """Crée un unique compte admin réel (pas de données de démo), à partir des variables
    d'environnement ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD. Utilisé quand DEMO_DATA=false sur
    une base vide : il n'existe aucune inscription publique, donc sans ça il n'y aurait aucun
    moyen de se connecter du tout après le premier démarrage."""
    username = os.environ.get('ADMIN_USERNAME')
    email = os.environ.get('ADMIN_EMAIL')
    password = os.environ.get('ADMIN_PASSWORD')
    if not (username and email and password):
        return
    admin = Users(username=username, email=email, password_hash=b'', salt=b'')
    admin.set_password(password)
    DB.session.add(admin)
    DB.session.flush()
    DB.session.add(UserRoles(user_id=admin.id, role_id=uuid.UUID('00000000-cafe-4bca-82bb-a0cec8e5a6ba')))
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
        Roles(id=VAR_STANDARD_USER_ROLE_ID, name="Standard user", description="Default user role with only rights on its own data")
    ]
    for role in roles:
        DB.session.add(role)
    DB.session.commit()


def assign_permissions_to_roles():
    admin_role_id = Roles.query.filter(Roles.name == "Global administrator").first().id
    standard_role_id = Roles.query.filter(Roles.name == "Standard user").first().id
    all_perms = Permissions.query.all()

    for perm in all_perms:
        # Admin : toutes les permissions. Standard user : tous les modules métier sauf
        # "Delete users" (gestion des comptes réservée à l'admin).
        DB.session.add(RolePermissions(role_id=admin_role_id, permission_id=perm.id))
        if perm.name != "Delete users":
            DB.session.add(RolePermissions(role_id=standard_role_id, permission_id=perm.id))
    DB.session.commit()


def ensure_permissions_up_to_date():
    """Ajoute les Permissions/RolePermissions manquantes vs VAR_PERMISSIONS_LIST sans toucher à
    l'existant. Contrairement à insert_permissions()/assign_permissions_to_roles(), tourne à
    CHAQUE démarrage (pas seulement sur base vide) — sinon une permission ajoutée après le seed
    initial (ex: 'Fiscalité') n'atteint jamais les installations déjà en place."""
    admin_role = Roles.query.filter(Roles.name == "Global administrator").first()
    standard_role = Roles.query.filter(Roles.name == "Standard user").first()
    if not admin_role or not standard_role:
        return
    existing_ids = {p.id for p in Permissions.query.all()}
    changed = False
    for name, meta in VAR_PERMISSIONS_LIST.items():
        if meta['id'] not in existing_ids:
            DB.session.add(Permissions(id=meta['id'], name=name, description=meta['description']))
            DB.session.add(RolePermissions(role_id=admin_role.id, permission_id=meta['id']))
            if name != "Delete users":
                DB.session.add(RolePermissions(role_id=standard_role.id, permission_id=meta['id']))
            changed = True
    if changed:
        DB.session.commit()

def seed_market_indices():
    """Peuple la table market_index si elle est vide."""
    if DB.session.query(MarketIndex).count() > 0:
        return
    from database.index_seed import build_index_data
    for index_name, tickers in build_index_data().items():
        seen = set()
        for ticker in tickers:
            t = ticker.strip().upper()
            if t and t not in seen:
                seen.add(t)
                DB.session.add(MarketIndex(index_name=index_name, ticker=t))
    DB.session.commit()

from scheduler import snapshot_wealth, start_scheduler
from utils.wealth import backfill_wealth_history

# RESET_DB_ON_START=true : repart d'une base vide + jeu de données de démo à chaque démarrage
# (comportement historique). Par défaut (false), les données existantes sont conservées entre
# deux redémarrages — seules les tables manquantes sont créées, et le seed initial (permissions,
# rôles, comptes de démo) n'est joué qu'une seule fois, tant que la base est vide.
RESET_DB_ON_START = os.environ.get('RESET_DB_ON_START', 'false').lower() == 'true'
# DEMO_DATA=true (par défaut) : peuple une base vide avec le jeu de données de test utilisé en dev
# (comptes Loris/Alice, transactions, budgets...). DEMO_DATA=false : base vide, seul un compte
# admin réel est créé si ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD sont fournis.
DEMO_DATA = os.environ.get('DEMO_DATA', 'true').lower() == 'true'

# Le reloader Werkzeug (debug=True) exécute tout ce module deux fois : une fois dans le processus
# "moniteur", qui relance ensuite un vrai processus enfant (WERKZEUG_RUN_MAIN=true). L'init DB (et
# le scheduler) ne doivent tourner qu'une fois — sinon les triggers Postgres sont créés en double
# (erreur) et les appels réseau (yfinance) sont dupliqués à chaque démarrage.
# USE_RELOADER=false dans Docker (voir Dockerfile) : le code n'y est de toute façon pas modifié à
# chaud, et le rechargeur y détecte parfois un faux changement au démarrage (système de fichiers
# du conteneur), ce qui redéclencherait exactement ce double-run.
USE_RELOADER = os.environ.get('FLASK_USE_RELOADER', 'true').lower() == 'true'
IS_MAIN_PROCESS = not (app.debug and USE_RELOADER) or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'

if IS_MAIN_PROCESS:
    with app.app_context():
        if RESET_DB_ON_START:
            reset_db()
        else:
            create_tables()

        if Users.query.count() == 0:
            insert_permissions()
            insert_roles()
            assign_permissions_to_roles()
            if DEMO_DATA:
                init_db()
            else:
                create_first_admin()

        ensure_permissions_up_to_date()

        seed_market_indices()
        # Reconstruit l'historique depuis la date d'achat la plus ancienne (prix/FX historiques via yfinance),
        # puis snapshot_wealth() écrase le point du jour avec des données live fraîches.
        backfill_wealth_history(DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations)
        snapshot_wealth(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, WealthSnapshot)

    start_scheduler(app, DB, Subscriptions, Transactions, Splits, Accounts, Assets, Commodities, FxRates,
                     AssetPossession, AssetDisposal, WealthSnapshot, UserSettings, TransactionDocuments, AssetValuations,
                     Loans, LoanInstallments)

uuid.uuid4()
if __name__ == '__main__':
    # host=0.0.0.0 : nécessaire pour être joignable depuis l'extérieur du conteneur Docker
    # (127.0.0.1, le défaut Flask, ne serait accessible que depuis l'intérieur du conteneur).
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=USE_RELOADER)


