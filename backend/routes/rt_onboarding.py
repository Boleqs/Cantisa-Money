from flask import request
from marshmallow import Schema, fields, ValidationError, validate
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response

# Alignée sur la contrainte CHECK réellement en base (migration e4a7c1f9b2d3) — le modèle
# SQLAlchemy accounts.py est resté obsolète sur ce point (n'y liste pas 'Liability').
ACCOUNT_TYPES = ('Income', 'Expense', 'Equity', 'Assets', 'Current', 'Liability')

# Plan de comptes standard proposé au premier login — repris du jeu de démo (app.py::init_db()),
# débarrassé du branding et du compte multi-devise (hors sujet pour un point de départ minimal).
PRESET_ACCOUNTS = [
    {'name': 'Compte courant',      'account_type': 'Current', 'description': 'Compte bancaire principal'},
    {'name': 'Épargne',             'account_type': 'Assets',  'description': "Compte d'épargne"},
    {'name': 'Salaires',            'account_type': 'Income',  'description': 'Source de revenus'},
    {'name': 'Dépenses courantes',  'account_type': 'Expense', 'description': 'Dépenses quotidiennes'},
]
PRESET_CATEGORIES = [
    {'name': 'Alimentation', 'description': 'Courses, restaurants'},
    {'name': 'Transport',    'description': 'Essence, transports en commun'},
    {'name': 'Loisirs',      'description': 'Sorties, voyages, abonnements'},
    {'name': 'Santé',        'description': 'Médecins, pharmacie'},
    {'name': 'Logement',     'description': 'Loyer, charges'},
]


class OnboardingAccountSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=128))
    account_type = fields.String(required=True, validate=validate.OneOf(ACCOUNT_TYPES))


class OnboardingSetupSchema(Schema):
    currency_name = fields.String(required=True, validate=validate.Length(min=1, max=128))
    currency_short_name = fields.String(required=True, validate=validate.Length(min=1, max=6))
    currency_fraction = fields.Integer(load_default=2, validate=validate.Range(min=0, max=8))
    mode = fields.String(required=True, validate=validate.OneOf(['preset', 'manual']))
    accounts = fields.List(fields.Nested(OnboardingAccountSchema), load_default=list)


class OnboardingRoutes:
    def __init__(self, app, DB, UserSettings, Commodities, Accounts, Categories):
        ROUTE_PATH = f"{ROOT_PATH}/onboarding"

        @app.route(f"{ROUTE_PATH}/setup", methods=['POST'])
        @jwt_required()
        def onboarding_setup():
            user_id = get_jwt_identity()
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            if settings and settings.onboarding_completed:
                return json_response('Onboarding already completed', HttpCode.CONFLICT)

            try:
                data = OnboardingSetupSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data['mode'] == 'manual' and not data['accounts']:
                return json_response(
                    'Au moins un compte est requis', HttpCode.BAD_REQUEST)

            account_defs = PRESET_ACCOUNTS if data['mode'] == 'preset' else data['accounts']
            requested_names = {a['name'] for a in account_defs}
            existing = Accounts.query.filter(
                Accounts.user_id == user_id, Accounts.name.in_(requested_names)).first()
            if existing:
                return json_response(
                    f"Un compte nommé « {existing.name} » existe déjà", HttpCode.CONFLICT)

            try:
                short_name = data['currency_short_name'].strip().upper()
                commodity = Commodities.query.filter_by(
                    user_id=user_id, short_name=short_name).first()
                if not commodity:
                    commodity = Commodities(
                        user_id=user_id,
                        name=data['currency_name'].strip(),
                        short_name=short_name,
                        type='Currency',
                        fraction=data['currency_fraction'],
                    )
                    DB.session.add(commodity)
                    DB.session.flush()

                created_accounts = []
                for a in account_defs:
                    account = Accounts(
                        user_id=user_id,
                        name=a['name'],
                        account_type=a['account_type'],
                        currency_id=commodity.id,
                        description=a.get('description'),
                        is_virtual=False,
                        is_hidden=False,
                    )
                    DB.session.add(account)
                    created_accounts.append(account)

                created_categories = []
                if data['mode'] == 'preset':
                    for c in PRESET_CATEGORIES:
                        if not Categories.query.filter_by(user_id=user_id, name=c['name']).first():
                            category = Categories(
                                user_id=user_id, name=c['name'], description=c['description'])
                            DB.session.add(category)
                            created_categories.append(category)

                if not settings:
                    settings = UserSettings(user_id=user_id)
                    DB.session.add(settings)
                settings.currency = short_name
                settings.onboarding_completed = True

                DB.session.flush()
                response = {
                    'currency': short_name,
                    'accounts': [a.name for a in created_accounts],
                    'categories': [c.name for c in created_categories],
                }
                DB.session.commit()
                return json_response(response, HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
