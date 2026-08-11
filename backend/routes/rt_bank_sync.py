import uuid
from datetime import datetime, timedelta

from marshmallow import Schema, fields, ValidationError
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.enable_banking import (
    EnableBankingError, is_configured, list_aspsps, start_authorization, create_session,
    get_account_transactions, get_app_id, get_redirect_url, save_config,
)
from backend.routes.rt_import import _match_rule

BANK_SYNC_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']
# Config globale de l'intégration (app_id / clé privée / redirect_url), pas une donnée utilisateur —
# gated par la permission admin existante (même perm que /admin/users, /admin/roles, /admin/backup).
ADMIN_PERM = VAR_PERMISSIONS_LIST['Administration']['id']

# Un seul provider câblé pour l'instant (phase 1) — les colonnes du schéma (bank_connections,
# institutions.sync_provider) restent génériques pour en accueillir d'autres plus tard.
SYNC_PROVIDER = 'enable_banking'

# Registres {sync_provider: fonction} utilisés par callback() et sync_connection() pour dispatcher
# vers la bonne implémentation selon bank_connections.sync_provider — un futur 2e provider s'ajoute
# ici sans toucher aux routes (la route de callback ne dépend pas du provider non plus, voir
# BankSyncCallback.vue : c'est le `state`, généré par Cantisa, qui l'identifie).
SYNC_SESSION_EXCHANGERS = {
    'enable_banking': create_session,
}
SYNC_TRANSACTION_FETCHERS = {
    'enable_banking': get_account_transactions,
}

# Fenêtre de récupération par défaut lors d'un premier sync (pas de last_synced_at encore connu).
DEFAULT_SYNC_LOOKBACK_DAYS = 90
# Durée de validité de consentement demandée à l'autorisation. Enable Banking documente 180 jours
# comme maximum global, mais certains ASPSP refusent une valeur pile égale (erreur 422 "does not
# support consent validity more than 15552000 seconds in the future") — marge de sécurité à 179.
CONSENT_VALID_DAYS = 179


class AspspsSchema(Schema):
    country = fields.String(required=True)


class AuthorizeSchema(Schema):
    aspsp_name = fields.String(required=True)
    aspsp_country = fields.String(required=True)
    institution_id = fields.UUID(required=False, load_default=None, allow_none=True)


class CallbackSchema(Schema):
    code = fields.String(required=True)
    state = fields.UUID(required=True)


class LinkSchema(Schema):
    account_id = fields.UUID(required=True)


def _connection_to_dict(c):
    return {
        'id': str(c.id),
        'institution_id': str(c.institution_id) if c.institution_id else None,
        'account_id': str(c.account_id) if c.account_id else None,
        'aspsp_name': c.aspsp_name,
        'aspsp_country': c.aspsp_country,
        'external_account_name': c.external_account_name,
        'external_account_currency': c.external_account_currency,
        'status': c.status,
        'valid_until': c.valid_until.isoformat() if c.valid_until else None,
        'last_synced_at': c.last_synced_at.isoformat() if c.last_synced_at else None,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


class BankSyncRoutes:
    def __init__(self, app, DB, BankConnections, Accounts, Institutions, Transactions, Splits, ImportCategoryRules, Users):
        ROUTE_PATH = f"{ROOT_PATH}/bank-sync"
        ADMIN_ROUTE_PATH = f"{ROOT_PATH}/admin/bank-sync"

        @app.route(f"{ADMIN_ROUTE_PATH}/config", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def get_bank_sync_config():
            return json_response({
                'app_id': get_app_id(),
                'redirect_url': get_redirect_url(),
                'key_configured': is_configured(),
            }, HttpCode.OK)

        @app.route(f"{ADMIN_ROUTE_PATH}/config", methods=['PUT'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def update_bank_sync_config():
            app_id = request.form.get('app_id')
            redirect_url = request.form.get('redirect_url')
            key_file = request.files.get('private_key')
            private_key = None
            if key_file:
                try:
                    private_key = key_file.read().decode('utf-8')
                except UnicodeDecodeError:
                    return json_response("Fichier de clé illisible (attendu : .pem en texte)", HttpCode.BAD_REQUEST)
            try:
                save_config(app_id=app_id, redirect_url=redirect_url, private_key=private_key)
            except EnableBankingError as e:
                return json_response(str(e), HttpCode.BAD_REQUEST)
            return json_response({
                'app_id': get_app_id(),
                'redirect_url': get_redirect_url(),
                'key_configured': is_configured(),
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/aspsps", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, BANK_SYNC_PERM)
        def get_aspsps():
            try:
                data = AspspsSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            if not is_configured():
                return json_response(
                    "Synchro bancaire non configurée (clé Enable Banking manquante)", HttpCode.SERVER_ERROR
                )
            try:
                aspsps = list_aspsps(data['country'].upper())
            except EnableBankingError as e:
                return json_response(str(e), HttpCode.SERVER_ERROR)
            return json_response(
                [{'name': a.get('name'), 'country': a.get('country'), 'logo': a.get('logo')} for a in aspsps],
                HttpCode.OK
            )

        @app.route(f"{ROUTE_PATH}/authorize", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, BANK_SYNC_PERM)
        def authorize():
            try:
                data = AuthorizeSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            if not is_configured():
                return json_response(
                    "Synchro bancaire non configurée (clé Enable Banking manquante)", HttpCode.SERVER_ERROR
                )

            user_id = get_jwt_identity()

            institution_id = data.get('institution_id')
            if institution_id:
                institution = Institutions.query.filter(
                    Institutions.id == institution_id, Institutions.user_id == user_id
                ).first()
                if not institution:
                    return json_response('Institution introuvable', HttpCode.NOT_FOUND)

            redirect_url = get_redirect_url()
            state = uuid.uuid4()
            valid_until = (datetime.now() + timedelta(days=CONSENT_VALID_DAYS)).strftime('%Y-%m-%dT%H:%M:%S.000Z')

            try:
                result = start_authorization(
                    data['aspsp_name'], data['aspsp_country'].upper(), redirect_url, state, valid_until
                )
            except EnableBankingError as e:
                return json_response(str(e), HttpCode.SERVER_ERROR)

            try:
                # Trace juste la demande en cours (compte(s) inconnus tant que la banque n'a pas
                # répondu) — voir callback() ci-dessous pour la création d'une ligne par compte
                # réellement autorisé une fois le code échangé. institution_id est déjà connu ici
                # (bouton "Connecter" cliqué depuis une institution précise) et propagé telle quelle.
                conn = BankConnections(
                    user_id=user_id,
                    institution_id=institution_id,
                    sync_provider=SYNC_PROVIDER,
                    aspsp_name=data['aspsp_name'],
                    aspsp_country=data['aspsp_country'].upper(),
                    state=state,
                    status='pending',
                )
                DB.session.add(conn)
                DB.session.commit()
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

            return json_response({'url': result.get('url')}, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/callback", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, BANK_SYNC_PERM)
        def callback():
            try:
                data = CallbackSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            conn = BankConnections.query.filter(
                BankConnections.state == data['state'],
                BankConnections.user_id == user_id,
                BankConnections.status == 'pending',
            ).first()
            if not conn:
                return json_response("Demande d'autorisation introuvable ou déjà traitée", HttpCode.NOT_FOUND)

            exchange_session = SYNC_SESSION_EXCHANGERS.get(conn.sync_provider)
            if not exchange_session:
                conn.status = 'error'
                DB.session.commit()
                return json_response(f"Provider de synchro inconnu : {conn.sync_provider}", HttpCode.SERVER_ERROR)

            try:
                session = exchange_session(data['code'])
            except EnableBankingError as e:
                conn.status = 'error'
                DB.session.commit()
                return json_response(str(e), HttpCode.SERVER_ERROR)

            accounts = session.get('accounts') or []
            if not accounts:
                conn.status = 'error'
                DB.session.commit()
                return json_response("Aucun compte renvoyé par la banque", HttpCode.SERVER_ERROR)

            # La banque peut autoriser l'accès à plusieurs comptes en une seule fois (ex: courant +
            # livret) — chacun devient une ligne 'needs_linking' distincte, à mapper explicitement
            # à un compte Cantisa via PATCH .../link plutôt que de deviner lequel l'utilisateur
            # voulait (voir historique : la version précédente prenait le premier à l'aveugle).
            session_id = session.get('session_id')
            new_connections = []
            try:
                for i, acc in enumerate(accounts):
                    target = conn if i == 0 else BankConnections(
                        user_id=user_id, institution_id=conn.institution_id, sync_provider=SYNC_PROVIDER,
                        aspsp_name=conn.aspsp_name, aspsp_country=conn.aspsp_country,
                    )
                    target.session_id = session_id
                    target.external_account_uid = acc.get('uid')
                    target.external_account_name = acc.get('name') or acc.get('product')
                    target.external_account_currency = acc.get('currency')
                    target.status = 'needs_linking'
                    target.state = None
                    if target is not conn:
                        DB.session.add(target)
                    new_connections.append(target)
                DB.session.commit()
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

            return json_response([_connection_to_dict(c) for c in new_connections], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/connections/<connection_id>/link", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, BANK_SYNC_PERM)
        def link_connection(connection_id):
            try:
                data = LinkSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            conn = BankConnections.query.filter(
                BankConnections.id == connection_id, BankConnections.user_id == user_id
            ).first()
            if not conn:
                return json_response('Connexion introuvable', HttpCode.NOT_FOUND)
            if conn.status != 'needs_linking':
                return json_response("Cette connexion n'est pas en attente de liaison", HttpCode.BAD_REQUEST)

            account = Accounts.query.filter(
                Accounts.id == data['account_id'], Accounts.user_id == user_id
            ).first()
            if not account:
                return json_response('Compte introuvable', HttpCode.NOT_FOUND)

            already_linked = BankConnections.query.filter(
                BankConnections.account_id == account.id,
                BankConnections.status == 'connected',
            ).first()
            if already_linked:
                return json_response('Ce compte Cantisa est déjà lié à une autre connexion bancaire', HttpCode.CONFLICT)

            try:
                conn.account_id = account.id
                # institution_id vient normalement déjà du bouton "Connecter" cliqué sur une
                # institution précise (voir authorize()) ; secours seulement si absent (connexion
                # créée sans institution, ex. anciennes connexions de test).
                if not conn.institution_id:
                    conn.institution_id = account.institution_id
                conn.status = 'connected'
                account.external_account_uid = conn.external_account_uid
                DB.session.commit()
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

            return json_response(_connection_to_dict(conn), HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/connections/<connection_id>", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, BANK_SYNC_PERM)
        def delete_connection(connection_id):
            user_id = get_jwt_identity()
            conn = BankConnections.query.filter(
                BankConnections.id == connection_id, BankConnections.user_id == user_id
            ).first()
            if not conn:
                return json_response('Connexion introuvable', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(conn)
                DB.session.commit()
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
            return json_response('Connexion supprimée', HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/connections", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, BANK_SYNC_PERM)
        def get_connections():
            conns = BankConnections.query.filter(
                BankConnections.user_id == get_jwt_identity()
            ).order_by(BankConnections.created_at.desc()).all()
            return json_response([_connection_to_dict(c) for c in conns], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/connections/<connection_id>/sync", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, BANK_SYNC_PERM)
        def sync_connection(connection_id):
            user_id = get_jwt_identity()
            conn = BankConnections.query.filter(
                BankConnections.id == connection_id, BankConnections.user_id == user_id
            ).first()
            if not conn:
                return json_response('Connexion introuvable', HttpCode.NOT_FOUND)
            if conn.status != 'connected' or not conn.external_account_uid:
                return json_response('Connexion non active', HttpCode.BAD_REQUEST)

            account = Accounts.query.filter(
                Accounts.id == conn.account_id, Accounts.user_id == user_id
            ).first()
            if not account:
                return json_response('Compte Cantisa associé introuvable', HttpCode.NOT_FOUND)

            fetch_transactions = SYNC_TRANSACTION_FETCHERS.get(conn.sync_provider)
            if not fetch_transactions:
                return json_response(f"Provider de synchro inconnu : {conn.sync_provider}", HttpCode.SERVER_ERROR)

            date_from = (conn.last_synced_at or datetime.now() - timedelta(days=DEFAULT_SYNC_LOOKBACK_DAYS))
            try:
                raw_transactions = fetch_transactions(
                    conn.external_account_uid, date_from=date_from.strftime('%Y-%m-%d')
                )
            except EnableBankingError as e:
                return json_response(str(e), HttpCode.SERVER_ERROR)

            rules_by_keyword = {
                r.keyword: r for r in ImportCategoryRules.query.filter_by(user_id=user_id).all()
            }

            parsed = []
            for i, t in enumerate(raw_transactions):
                amount_raw = t.get('transaction_amount', {})
                try:
                    amount = float(amount_raw.get('amount', 0))
                except (TypeError, ValueError):
                    continue
                if t.get('credit_debit_indicator') != 'CRDT':
                    amount = -amount

                tx_date = t.get('booking_date') or t.get('value_date') or t.get('transaction_date')
                if not tx_date:
                    continue

                remittance = t.get('remittance_information') or []
                desc = ' '.join(r for r in remittance if r).strip()
                if not desc:
                    party = t.get('creditor') or t.get('debtor') or {}
                    desc = party.get('name', '')

                existing = Splits.query.join(
                    Transactions, Transactions.id == Splits.tx_id
                ).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id == account.id,
                    Transactions.post_date == datetime.strptime(tx_date, '%Y-%m-%d'),
                    Splits.quantity == amount,
                ).first()
                is_duplicate = existing is not None

                rule_category_id, rule_opposing_id = _match_rule(rules_by_keyword, desc)
                parsed.append({
                    'row': i,
                    'date': tx_date,
                    'description': desc,
                    'amount': amount,
                    'category_id': rule_category_id,
                    'opposing_account_id': rule_opposing_id,
                    'is_duplicate': is_duplicate,
                    'selected': not is_duplicate,
                })

            try:
                conn.last_synced_at = datetime.now()
                DB.session.commit()
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

            return json_response({
                'account_id': str(account.id),
                'currency_id': str(account.currency_id),
                'transactions': parsed,
            }, HttpCode.OK)
