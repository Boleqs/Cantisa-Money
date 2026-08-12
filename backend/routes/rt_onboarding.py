from flask import request
from marshmallow import Schema, fields, ValidationError, validate
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response

# Alignée sur la contrainte CHECK réellement en base (migration e4a7c1f9b2d3), même liste que le
# CheckConstraint de accounts.py.
ACCOUNT_TYPES = ('Income', 'Expense', 'Equity', 'Assets', 'Current', 'Liability')

# Plan de comptes standard proposé au premier login. Trois notions distinctes dans Cantisa,
# chacune répondant à sa propre question (voir discussion avec Loris, 2026-08-12) :
#   - Compte (Income/Expense)  → À QUI ? l'entité en face (employeur, bailleur, assureur…),
#     hiérarchique via parent_id, à la GnuCash. Les comptes courant/épargne restent en tête,
#     inchangés (rien à voir avec Income/Expense).
#   - Catégorie (plate)        → POURQUOI ? la raison/le poste budgétaire.
#   - Tag (plat, avec couleur) → QUOI ? la nature concrète du bien/service, transversale aux
#     catégories (un même tag "Vêtements" peut apparaître sous catégorie Habillement ou Cadeaux).
# 'parent' référence le 'name' d'une entrée précédente dans cette même liste (les parents sont
# toujours listés avant leurs enfants) ; 'virtual' marque les nœuds de regroupement purs, sans
# transaction directe attendue dessus (même logique que les comptes placeholder de GnuCash).
PRESET_ACCOUNTS = [
    {'name': 'Compte courant', 'account_type': 'Current', 'description': 'Compte bancaire principal'},
    {'name': 'Épargne',        'account_type': 'Assets',  'description': "Compte d'épargne"},

    # ── Revenus : à qui ? ───────────────────────────────────────────────
    {'name': 'Revenus', 'account_type': 'Income', 'virtual': True},
    {'name': 'Employeur(s)', 'account_type': 'Income', 'parent': 'Revenus', 'virtual': True},
    {'name': 'Employeur principal', 'account_type': 'Income', 'parent': 'Employeur(s)'},
    {'name': 'Clients (freelance / activité indépendante)', 'account_type': 'Income', 'parent': 'Revenus'},
    {'name': 'Établissement bancaire', 'account_type': 'Income', 'parent': 'Revenus', 'description': 'Intérêts, dividendes'},
    {'name': 'Locataire(s)', 'account_type': 'Income', 'parent': 'Revenus'},
    {'name': 'Organismes sociaux', 'account_type': 'Income', 'parent': 'Revenus', 'virtual': True},
    {'name': 'CAF / Prestations familiales', 'account_type': 'Income', 'parent': 'Organismes sociaux'},
    {'name': 'Pôle emploi', 'account_type': 'Income', 'parent': 'Organismes sociaux'},
    {'name': 'Administration fiscale', 'account_type': 'Income', 'parent': 'Revenus', 'description': 'Remboursements'},
    {'name': 'Particuliers', 'account_type': 'Income', 'parent': 'Revenus', 'description': 'Cadeaux reçus, remboursements entre proches'},

    # ── Dépenses : à qui ? ──────────────────────────────────────────────
    {'name': 'Dépenses', 'account_type': 'Expense', 'virtual': True},
    {'name': 'Bailleur / Agence immobilière', 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': 'Syndic de copropriété', 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': "Fournisseur d'énergie", 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': 'Opérateur télécom / internet', 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': 'Assureurs', 'account_type': 'Expense', 'parent': 'Dépenses', 'virtual': True},
    {'name': 'Assurance habitation', 'account_type': 'Expense', 'parent': 'Assureurs'},
    {'name': 'Assurance auto', 'account_type': 'Expense', 'parent': 'Assureurs'},
    {'name': 'Mutuelle santé', 'account_type': 'Expense', 'parent': 'Assureurs'},
    {'name': 'Établissement bancaire (frais)', 'account_type': 'Expense', 'parent': 'Dépenses', 'description': 'Frais, intérêts de crédit'},
    {'name': 'Administrations', 'account_type': 'Expense', 'parent': 'Dépenses', 'virtual': True},
    {'name': 'Trésor public', 'account_type': 'Expense', 'parent': 'Administrations'},
    {'name': 'Collectivités locales', 'account_type': 'Expense', 'parent': 'Administrations'},
    {'name': 'Grande distribution / Supermarchés', 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': 'Restaurants et cafés', 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': 'Transporteurs', 'account_type': 'Expense', 'parent': 'Dépenses', 'description': 'Train, bus, avion'},
    {'name': 'Professionnels de santé', 'account_type': 'Expense', 'parent': 'Dépenses', 'virtual': True},
    {'name': 'Médecins / Spécialistes', 'account_type': 'Expense', 'parent': 'Professionnels de santé'},
    {'name': 'Pharmacies', 'account_type': 'Expense', 'parent': 'Professionnels de santé'},
    {'name': 'Établissements scolaires / Garde d\'enfants', 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': 'Commerces / Boutiques', 'account_type': 'Expense', 'parent': 'Dépenses'},
    {'name': 'Particuliers (dépenses)', 'account_type': 'Expense', 'parent': 'Dépenses', 'description': 'Cadeaux donnés, prêts'},
]

# Pourquoi ? — plate (le modèle categories n'a pas de hiérarchie), alignée sur le 1er niveau de la
# logique de dépense/revenu plutôt que sur les comptes ci-dessus (eux répondent à "à qui").
PRESET_CATEGORIES = [
    {'name': 'Logement'},
    {'name': 'Alimentation'},
    {'name': 'Transport'},
    {'name': 'Santé'},
    {'name': 'Assurances'},
    {'name': 'Impôts et taxes'},
    {'name': 'Loisirs & sorties'},
    {'name': 'Habillement'},
    {'name': 'Éducation'},
    {'name': 'Famille & enfants'},
    {'name': 'Cadeaux & dons'},
    {'name': 'Salaire'},
    {'name': 'Revenus financiers'},
    {'name': 'Remboursements'},
    {'name': 'Autres revenus'},
]

# Quoi ? — plate, transversale aux catégories (ex: tag "Vêtements" utilisable aussi bien sous
# catégorie Habillement que Cadeaux & dons). Couleur parmi la palette fixe du modèle Tags.
PRESET_TAGS = [
    {'name': 'Alimentaire', 'color': 'green'},
    {'name': 'Vêtements', 'color': 'blue'},
    {'name': 'Électronique / High-tech', 'color': 'purple'},
    {'name': 'Carburant', 'color': 'yellow'},
    {'name': 'Facture / Abonnement', 'color': 'yellow'},
    {'name': 'Loyer', 'color': 'black'},
    {'name': 'Titre de transport', 'color': 'blue'},
    {'name': 'Loisir / Divertissement', 'color': 'purple'},
    {'name': 'Santé / Médicaments', 'color': 'red'},
    {'name': 'Matériel / Équipement', 'color': 'white'},
    {'name': 'Service / Prestation', 'color': 'white'},
    {'name': 'Cadeau', 'color': 'green'},
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
    def __init__(self, app, DB, UserSettings, Commodities, Accounts, Categories, Tags):
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

                # Les parents sont toujours listés avant leurs enfants dans account_defs (garanti
                # par construction de PRESET_ACCOUNTS) — un flush immédiat après chaque ajout
                # rend l'id disponible pour résoudre le parent_id des entrées suivantes via ce dict,
                # sans avoir besoin d'un vrai tri topologique.
                created_accounts = []
                accounts_by_name = {}
                for a in account_defs:
                    parent_name = a.get('parent')
                    account = Accounts(
                        user_id=user_id,
                        name=a['name'],
                        account_type=a['account_type'],
                        currency_id=commodity.id,
                        description=a.get('description'),
                        parent_id=accounts_by_name[parent_name].id if parent_name else None,
                        is_virtual=a.get('virtual', False),
                        is_hidden=False,
                    )
                    DB.session.add(account)
                    DB.session.flush()
                    created_accounts.append(account)
                    accounts_by_name[a['name']] = account

                created_categories = []
                created_tags = []
                if data['mode'] == 'preset':
                    for c in PRESET_CATEGORIES:
                        if not Categories.query.filter_by(user_id=user_id, name=c['name']).first():
                            category = Categories(
                                user_id=user_id, name=c['name'], description=c.get('description'))
                            DB.session.add(category)
                            created_categories.append(category)

                    for t in PRESET_TAGS:
                        if not Tags.query.filter_by(user_id=user_id, name=t['name']).first():
                            tag = Tags(user_id=user_id, name=t['name'], color=t['color'])
                            DB.session.add(tag)
                            created_tags.append(tag)

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
                    'tags': [t.name for t in created_tags],
                }
                DB.session.commit()
                return json_response(response, HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
