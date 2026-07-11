from marshmallow import Schema, fields, ValidationError
from sqlalchemy import func

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

RECONCILE_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']


class ConfirmReconcileSchema(Schema):
    account_id = fields.UUID(required=True)
    split_ids  = fields.List(fields.UUID(), required=True)


class ReconcileRoutes:
    def __init__(self, app, DB, Transactions, Splits, Accounts, Users):
        ROUTE_PATH = f"{ROOT_PATH}/reconcile"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, RECONCILE_PERM)
        def get_reconcile_data():
            account_id = request.args.get('account_id')
            if not account_id:
                return json_response('account_id requis', HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()

            # Vérifier que le compte appartient à l'utilisateur
            account = Accounts.query.filter_by(id=account_id, user_id=user_id).first()
            if not account:
                return json_response('Compte introuvable', HttpCode.NOT_FOUND)

            # Solde rapproché actuel = somme des splits réconciliés pour ce compte
            reconciled_balance = (
                DB.session.query(func.coalesce(func.sum(Splits.quantity), 0))
                .filter(Splits.account_id == account_id, Splits.is_reconciled == True)
                .scalar()
            )

            # Transactions non rapprochées pour ce compte (jointure avec Transactions)
            rows = (
                DB.session.query(Splits, Transactions)
                .join(Transactions, Transactions.id == Splits.tx_id)
                .filter(
                    Splits.account_id == account_id,
                    Splits.is_reconciled == False,
                    Transactions.user_id == user_id,
                )
                .order_by(Transactions.post_date.asc(), Transactions.id)
                .all()
            )

            pending = [
                {
                    'split_id':    str(sp.id),
                    'tx_id':       str(tx.id),
                    'date':        tx.post_date.strftime('%Y-%m-%d') if tx.post_date else None,
                    'description': tx.description or '',
                    'amount':      float(sp.quantity),
                    'is_cleared':  tx.is_cleared,
                }
                for sp, tx in rows
            ]

            return json_response({
                'account_id':        str(account.id),
                'account_name':      account.name,
                'reconciled_balance': float(reconciled_balance),
                'pending':           pending,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/confirm", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, RECONCILE_PERM)
        def confirm_reconcile():
            try:
                data = ConfirmReconcileSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            account_id = data['account_id']
            split_ids  = data['split_ids']

            # Sécurité : vérifier que tous les splits appartiennent à l'utilisateur et au compte
            splits = (
                Splits.query
                .join(Transactions, Transactions.id == Splits.tx_id)
                .filter(
                    Splits.id.in_(split_ids),
                    Splits.account_id == account_id,
                    Transactions.user_id == user_id,
                )
                .all()
            )

            if len(splits) != len(split_ids):
                return json_response('Certains splits sont invalides ou inaccessibles', HttpCode.BAD_REQUEST)

            try:
                for sp in splits:
                    sp.is_reconciled = True
                DB.session.commit()
                return json_response({'reconciled_count': len(splits)}, HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
