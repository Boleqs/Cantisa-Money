import uuid
from datetime import date, datetime, timedelta
from marshmallow import Schema, fields, ValidationError, validate
from sqlalchemy import func as sql_func
import hashlib

from flask import jsonify, request, make_response
import jwt
from flask_jwt_extended import (jwt_required, set_access_cookies, unset_jwt_cookies, get_jwt, create_access_token,
                                get_jwt_identity, create_refresh_token, set_refresh_cookies)

from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS as JWT_ACCESS_TOKEN_LIFETIME,
                            VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS,
                            VAR_PERMISSIONS_LIST
                            )
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response
from backend.utils.market_price import get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission

ACCOUNTS_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']
BALANCE_TOLERANCE = 0.01
# Tenu synchronisé avec TAX_TREATMENTS dans rt_tax.py.
TAX_TREATMENT_VALUES = ('taxable_income', 'deductible', 'real_estate_income', 'real_estate_expense')


class AddAccountSchema(Schema):
    name = fields.String(required=True)
    description = fields.String(load_default=None, allow_none=True)
    currency_id = fields.String(required=True)
    parent_id = fields.UUID()
    institution_id = fields.UUID(load_default=None, allow_none=True)
    account_type = fields.String()
    account_subtype = fields.String()
    is_virtual = fields.Boolean()
    is_hidden = fields.Boolean()
    code = fields.String()
    tax_treatment = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(TAX_TREATMENT_VALUES))
    # Solde initial optionnel (compte dont l'historique de transactions a été perdu lors de son
    # intégration à l'app) — voir _apply_opening_balance ci-dessous.
    opening_balance = fields.Float(load_default=None, allow_none=True)
    opening_balance_date = fields.Date(load_default=None, allow_none=True)


class UpdateAccountSchema(Schema):
    account_id = fields.UUID(required=True)
    name = fields.String(required=True)
    description = fields.String(load_default=None, allow_none=True)
    currency_id = fields.String(required=True)
    parent_id = fields.UUID()
    institution_id = fields.UUID(load_default=None, allow_none=True)
    account_type = fields.String()
    account_subtype = fields.String()
    is_virtual = fields.Boolean()
    is_hidden = fields.Boolean()
    is_closed = fields.Boolean()
    code = fields.String()
    tax_treatment = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(TAX_TREATMENT_VALUES))


class GetAccountSchema(Schema):
    account_id = fields.UUID()


class DeleteAccountSchema(Schema):
    account_id = fields.UUID(required=True)


class CloseAccountSchema(Schema):
    account_id = fields.UUID(required=True)
    # Compte de contrepartie pour la transaction d'équilibrage finale, requis seulement si
    # le compte à clôturer n'est pas déjà à zéro.
    balancing_account_id = fields.UUID(load_default=None)


class SetOpeningBalanceSchema(Schema):
    account_id = fields.UUID(required=True)
    amount = fields.Float(required=True)
    as_of_date = fields.Date(load_default=date.today)


class RemoveOpeningBalanceSchema(Schema):
    account_id = fields.UUID(required=True)


def _name_conflict(Accounts, user_id, name, parent_id, institution_id, exclude_account_id=None):
    """Unicité du nom scopée (voir accounts.py / uq_accounts_user_parent_name et
    uq_accounts_user_institution_name) : conflit seulement si un autre compte du même nom partage
    le même compte parent OU la même institution — un compte sans les deux n'a aucun scope contre
    lequel se comparer, donc jamais de conflit dans ce cas (comportement voulu, pas un oubli)."""
    if not parent_id and not institution_id:
        return False
    query = Accounts.query.filter(Accounts.user_id == user_id, Accounts.name == name)
    if exclude_account_id:
        query = query.filter(Accounts.id != exclude_account_id)
    if parent_id and query.filter(Accounts.parent_id == parent_id).first():
        return True
    if institution_id and query.filter(Accounts.institution_id == institution_id).first():
        return True
    return False


def _get_or_create_opening_equity_account(DB, Accounts, Commodities, user_id, currency_id):
    """Compte Equity de contrepartie pour les soldes initiaux de reprise, partagé par devise
    (un seul compte par devise, pas un par compte concerné) — convention comptable standard.
    Subtype 'opening_balance' pour l'exclure des listes de comptes (voir Accounts.vue), même
    logique que le subtype 'loan' des prêts déjà en cours."""
    account = Accounts.query.filter(
        Accounts.user_id == user_id,
        Accounts.account_type == 'Equity',
        Accounts.account_subtype == 'opening_balance',
        Accounts.currency_id == currency_id,
    ).first()
    if account:
        return account
    commodity = Commodities.query.filter_by(id=currency_id).first() if Commodities else None
    label = commodity.short_name.upper() if commodity and commodity.short_name else None
    account = Accounts(
        user_id=user_id,
        name=f"Solde d'ouverture ({label})" if label else "Solde d'ouverture",
        description="Contrepartie comptable générée automatiquement pour les soldes initiaux de reprise",
        account_type='Equity',
        account_subtype='opening_balance',
        currency_id=currency_id,
        is_virtual=False,
        is_hidden=True,
    )
    DB.session.add(account)
    DB.session.flush()
    return account


def _apply_opening_balance(DB, Accounts, Transactions, Splits, Commodities, user_id, account, amount, as_of_date):
    """Crée ou met à jour la transaction d'équilibrage du solde initial d'un compte. Les deux
    splits sont dans la même devise (le compte de contrepartie est créé par devise, voir
    _get_or_create_opening_equity_account) : pas de conversion de change nécessaire."""
    equity_account = _get_or_create_opening_equity_account(DB, Accounts, Commodities, user_id, account.currency_id)
    post_dt = datetime.combine(as_of_date, datetime.min.time())

    tx = None
    if account.opening_balance_transaction_id:
        tx = Transactions.query.filter_by(id=account.opening_balance_transaction_id).first()

    if tx:
        tx.post_date = post_dt
        tx.effective_date = post_dt
        account_split = Splits.query.filter_by(tx_id=tx.id, account_id=account.id).first()
        equity_split = Splits.query.filter(
            Splits.tx_id == tx.id, Splits.account_id != account.id).first()
        if account_split:
            account_split.quantity = amount
        if equity_split:
            equity_split.quantity = -amount
    else:
        tx = Transactions(
            user_id=user_id, currency_id=account.currency_id,
            post_date=post_dt, effective_date=post_dt,
            description=f"Solde d'ouverture — {account.name}", is_cleared=True,
        )
        DB.session.add(tx)
        DB.session.flush()
        DB.session.add(Splits(tx_id=tx.id, account_id=account.id, quantity=amount))
        DB.session.add(Splits(tx_id=tx.id, account_id=equity_account.id, quantity=-amount))
        account.opening_balance_transaction_id = tx.id


class AccountsRoutes:
    def __init__(self, app, DB, Users, Accounts, Splits=None, Transactions=None, Commodities=None, FxRates=None,
                 Institutions=None):
        ROUTE_PATH = f"{ROOT_PATH}/accounts"

        @app.route(f"{ROUTE_PATH}", methods=["POST"])
        @jwt_required()
        @restricted_by_permission(Users, ACCOUNTS_PERM)
        def add_account():
            try:
                # Validate request body against schema data types
                data = AddAccountSchema().load(request.json)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            try:
                parent_id = data.get('parent_id')
                institution_id = data.get('institution_id')
                if _name_conflict(Accounts, get_jwt_identity(), data.get("name"), parent_id, institution_id):
                    return json_response(
                        "Un compte de ce nom existe déjà sous ce compte parent ou cette institution",
                        HttpCode.CONFLICT)

                if parent_id:
                    parent = Accounts.query.filter(
                        Accounts.user_id == get_jwt_identity(),
                        Accounts.id == parent_id).first()
                    if not parent:
                        return json_response("Compte parent introuvable", HttpCode.BAD_REQUEST)
                    if str(parent.currency_id) != str(data.get('currency_id')):
                        return json_response(
                            "Le compte enfant doit avoir la même devise que son compte parent",
                            HttpCode.BAD_REQUEST)

                if institution_id and Institutions is not None:
                    institution = Institutions.query.filter(
                        Institutions.user_id == get_jwt_identity(),
                        Institutions.id == institution_id).first()
                    if not institution:
                        return json_response("Institution introuvable", HttpCode.BAD_REQUEST)

                account = Accounts(
                    user_id=get_jwt_identity(),
                    name=data.get("name"),
                    description=data.get("description"),
                    currency_id=data.get("currency_id"),
                    parent_id=data.get("parent_id"),
                    institution_id=institution_id,
                    account_type=data.get("account_type"),
                    account_subtype=data.get("account_subtype"),
                    is_virtual=data.get("is_virtual", False),
                    is_hidden=data.get("is_hidden", False),
                    code=data.get("code"),
                    tax_treatment=data.get("tax_treatment"),
                )
                DB.session.add(account)
                DB.session.flush()

                opening_balance = data.get('opening_balance')
                if opening_balance and account.account_type not in ('Income', 'Expense'):
                    _apply_opening_balance(
                        DB, Accounts, Transactions, Splits, Commodities, get_jwt_identity(),
                        account, opening_balance, data.get('opening_balance_date') or date.today())

                DB.session.commit()
                return json_response(account, HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=["PATCH"])
        @jwt_required()
        @restricted_by_permission(Users, ACCOUNTS_PERM)
        def update_account():
            try:
                # Validate request body against schema data types
                data = UpdateAccountSchema().load(request.json)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            account = Accounts.query.filter(
                Accounts.user_id == get_jwt_identity(),
                Accounts.id == data.get('account_id')).first()
            if not account:
                return json_response('Account does not exist', HttpCode.NOT_FOUND)

            new_parent_id = data.get('parent_id')
            if new_parent_id:
                ancestor_id = new_parent_id
                while ancestor_id is not None:
                    if ancestor_id == account.id:
                        return json_response(
                            "Ce compte ne peut pas être son propre ancêtre",
                            HttpCode.BAD_REQUEST)
                    ancestor = Accounts.query.filter(Accounts.id == ancestor_id).first()
                    ancestor_id = ancestor.parent_id if ancestor else None

            # Devise verrouillée sur toute la chaîne parent/enfant (sinon les totaux consolidés,
            # qui additionnent brut sans conversion, deviennent faux) : on vérifie le parent effectif
            # (celui du payload, ou l'actuel si non fourni — la devise peut changer sans reparentage)
            # et les enfants directs existants.
            effective_parent_id = data.get('parent_id', account.parent_id)
            new_currency_id = data.get('currency_id')
            if effective_parent_id:
                parent = Accounts.query.filter(Accounts.id == effective_parent_id).first()
                if parent and str(parent.currency_id) != str(new_currency_id):
                    return json_response(
                        "Le compte enfant doit avoir la même devise que son compte parent",
                        HttpCode.BAD_REQUEST)
            mismatched_child = Accounts.query.filter(
                Accounts.parent_id == account.id,
                Accounts.currency_id != new_currency_id
            ).first()
            if mismatched_child:
                return json_response(
                    "Impossible de changer la devise : au moins un compte enfant a une devise différente",
                    HttpCode.BAD_REQUEST)

            new_institution_id = data.get('institution_id')
            if new_institution_id and Institutions is not None:
                institution = Institutions.query.filter(
                    Institutions.user_id == get_jwt_identity(),
                    Institutions.id == new_institution_id).first()
                if not institution:
                    return json_response("Institution introuvable", HttpCode.BAD_REQUEST)

            if _name_conflict(Accounts, get_jwt_identity(), data.get('name'), effective_parent_id,
                               new_institution_id, exclude_account_id=account.id):
                return json_response(
                    "Un compte de ce nom existe déjà sous ce compte parent ou cette institution",
                    HttpCode.CONFLICT)

            # Champs requis par le schéma : toujours présents. Les autres sont optionnels
            # (le client peut les omettre) -> on garde alors la valeur actuelle du compte
            # plutôt que de l'écraser par None (ce qui plantait sur les colonnes NOT NULL
            # account_type/is_virtual/is_hidden).
            account.name = data.get('name')
            account.description = data.get('description')
            account.currency_id = data.get('currency_id')
            account.parent_id = data.get('parent_id', account.parent_id)
            account.institution_id = new_institution_id
            account.account_type = data.get('account_type', account.account_type)
            account.account_subtype = data.get('account_subtype', account.account_subtype)
            account.is_virtual = data.get('is_virtual', account.is_virtual)
            account.is_hidden = data.get('is_hidden', account.is_hidden)
            # Réouverture d'un compte clôturé (close_account ci-dessous) : pas de ré-équilibrage à
            # faire dans l'autre sens, on repasse juste le flag (et closed_at) — l'historique des
            # transactions, lui, reste tel quel.
            new_is_closed = data.get('is_closed', account.is_closed)
            if new_is_closed != account.is_closed:
                account.is_closed = new_is_closed
                account.closed_at = datetime.now() if new_is_closed else None
            account.code = data.get('code', account.code)
            account.tax_treatment = data.get('tax_treatment')
            DB.session.commit()
            return json_response(account, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=["GET"])
        @jwt_required()
        @restricted_by_permission(Users, ACCOUNTS_PERM)
        def get_account():
            try:
                # Validate request body against schema data types
                data = GetAccountSchema().load(request.args)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            # If user only wants one account
            if data.get('account_id'):
                return json_response(Accounts.query.filter(
                    Accounts.user_id == get_jwt_identity(),
                    Accounts.id == data.get("account_id")).first(), HttpCode.OK)
            # Else return all accounts of user
            return json_response(
                Accounts.query.filter(Accounts.user_id == get_jwt_identity()).all(), HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=["DELETE"])
        @jwt_required()
        @restricted_by_permission(Users, ACCOUNTS_PERM)
        def delete_account():
            try:
                # Validate request body against schema data types
                data = DeleteAccountSchema().load(request.args)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            try:
                account_to_delete = Accounts.query.filter(
                    Accounts.user_id == get_jwt_identity(),
                    Accounts.id == data.get('account_id')).first()
                if not account_to_delete:
                    return json_response("Account doesn't exist", HttpCode.NOT_FOUND)
                # splits.account_id est en ON DELETE CASCADE (pas SET NULL) : supprimer un compte
                # qui a des splits supprimerait ces lignes sans toucher aux transactions qui les
                # portent, laissant des transactions orphelines avec des splits déséquilibrés (bug
                # constaté en prod sur la suppression d'un prêt soldé, cf. delete_loan()). On bloque
                # donc la suppression tant que le compte a des mouvements, plutôt que de la laisser
                # corrompre silencieusement l'historique.
                if Splits is not None and Splits.query.filter(Splits.account_id == account_to_delete.id).first():
                    return json_response(
                        "Impossible de supprimer un compte qui a des transactions — "
                        "supprimez ou déplacez d'abord ses transactions",
                        HttpCode.CONFLICT)
                DB.session.delete(account_to_delete)
                DB.session.commit()
                return json_response('Account has been deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/close", methods=["POST"])
        @jwt_required()
        @restricted_by_permission(Users, ACCOUNTS_PERM)
        def close_account():
            try:
                data = CloseAccountSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            account = Accounts.query.filter(
                Accounts.user_id == user_id, Accounts.id == data['account_id']).first()
            if not account:
                return json_response('Compte introuvable', HttpCode.NOT_FOUND)
            if account.is_closed:
                return json_response('Ce compte est déjà clôturé', HttpCode.BAD_REQUEST)

            balance = float(
                DB.session.query(sql_func.coalesce(sql_func.sum(Splits.quantity), 0))
                .filter(Splits.account_id == account.id).scalar() or 0
            )

            try:
                if abs(balance) > BALANCE_TOLERANCE:
                    balancing_id = data.get('balancing_account_id')
                    if not balancing_id:
                        # Compte non soldé et pas de contrepartie fournie : on renvoie le solde pour
                        # que le frontend propose de créer la transaction d'équilibrage plutôt que
                        # d'échouer sèchement.
                        return json_response({
                            'needs_balancing': True,
                            'balance': round(balance, 2),
                            'currency_id': str(account.currency_id),
                        }, HttpCode.CONFLICT)

                    balancing_account = Accounts.query.filter(
                        Accounts.user_id == user_id, Accounts.id == balancing_id).first()
                    if not balancing_account:
                        return json_response('Compte de contrepartie introuvable', HttpCode.NOT_FOUND)
                    if str(balancing_account.id) == str(account.id):
                        return json_response(
                            'Le compte de contrepartie doit être différent du compte à clôturer',
                            HttpCode.BAD_REQUEST)

                    # Transaction d'équilibrage : le compte à clôturer reçoit -balance (le ramène à
                    # zéro), la contrepartie reçoit l'équivalent converti dans sa propre devise —
                    # même convention que _resolve_split_fx_rates dans rt_transactions.py (quantity
                    # dans la devise du compte du split, fx_rate = taux vers la devise de la tx).
                    today = date.today()
                    account_commodity = Commodities.query.filter_by(id=account.currency_id).first() if Commodities else None
                    balancing_commodity = Commodities.query.filter_by(id=balancing_account.currency_id).first() if Commodities else None
                    account_code = account_commodity.short_name if account_commodity else None
                    balancing_code = balancing_commodity.short_name if balancing_commodity else None

                    fx_rate_balancing = 1.0
                    if account_code and balancing_code and account_code != balancing_code and FxRates:
                        fx_rate_balancing = get_fx_rate(balancing_code, account_code, FxRates, on_date=today) or 1.0

                    post_dt = datetime.combine(today, datetime.min.time())
                    tx = Transactions(
                        user_id=user_id, currency_id=account.currency_id,
                        post_date=post_dt, effective_date=post_dt,
                        description=f"Clôture du compte — {account.name}", is_cleared=True,
                    )
                    DB.session.add(tx)
                    DB.session.flush()
                    DB.session.add(Splits(tx_id=tx.id, account_id=account.id, quantity=-balance))
                    DB.session.add(Splits(
                        tx_id=tx.id, account_id=balancing_account.id,
                        quantity=round(balance / fx_rate_balancing, 2),
                        fx_rate=fx_rate_balancing,
                    ))

                account.is_closed = True
                account.is_hidden = True
                account.closed_at = datetime.now()
                DB.session.commit()
                return json_response(account, HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/opening-balance", methods=["POST"])
        @jwt_required()
        @restricted_by_permission(Users, ACCOUNTS_PERM)
        def set_opening_balance():
            """Renseigne (ou met à jour) le solde initial d'un compte dont l'historique de
            transactions a été perdu lors de son intégration à l'app — génère/actualise une
            transaction d'équilibrage contre un compte Equity partagé par devise (voir
            _apply_opening_balance)."""
            try:
                data = SetOpeningBalanceSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            account = Accounts.query.filter(
                Accounts.user_id == user_id, Accounts.id == data['account_id']).first()
            if not account:
                return json_response('Compte introuvable', HttpCode.NOT_FOUND)
            if account.account_type in ('Income', 'Expense'):
                return json_response(
                    "Un solde initial n'a pas de sens pour un compte de contrepartie",
                    HttpCode.BAD_REQUEST)
            if account.account_subtype in ('loan', 'opening_balance'):
                return json_response(
                    "Ce compte est géré automatiquement, pas de solde initial manuel",
                    HttpCode.BAD_REQUEST)
            if data['amount'] == 0:
                return json_response(
                    "Le montant doit être différent de zéro — utilisez la suppression pour "
                    "retirer un solde initial",
                    HttpCode.BAD_REQUEST)

            try:
                _apply_opening_balance(
                    DB, Accounts, Transactions, Splits, Commodities, user_id,
                    account, data['amount'], data['as_of_date'])
                DB.session.commit()
                return json_response(account, HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/opening-balance", methods=["DELETE"])
        @jwt_required()
        @restricted_by_permission(Users, ACCOUNTS_PERM)
        def remove_opening_balance():
            try:
                data = RemoveOpeningBalanceSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            account = Accounts.query.filter(
                Accounts.user_id == user_id, Accounts.id == data['account_id']).first()
            if not account:
                return json_response('Compte introuvable', HttpCode.NOT_FOUND)
            if not account.opening_balance_transaction_id:
                return json_response("Ce compte n'a pas de solde initial", HttpCode.BAD_REQUEST)

            try:
                tx_id = account.opening_balance_transaction_id
                account.opening_balance_transaction_id = None
                DB.session.flush()
                tx = Transactions.query.filter_by(id=tx_id).first()
                if tx:
                    DB.session.delete(tx)
                DB.session.commit()
                return json_response(account, HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

