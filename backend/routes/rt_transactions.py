import uuid
from datetime import datetime
from marshmallow import Schema, fields, ValidationError

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH)
from backend.utils.api_responses import json_response


class SplitInputSchema(Schema):
    account_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True)


class AddTransactionSchema(Schema):
    description = fields.String(load_default=None)
    currency_id = fields.UUID(required=True)
    post_date = fields.String(required=True)
    effective_date = fields.String(load_default=None)
    category_id = fields.UUID(load_default=None)
    is_cleared = fields.Boolean(load_default=False)
    splits = fields.List(fields.Nested(SplitInputSchema), required=True)


class UpdateTransactionSchema(Schema):
    transaction_id = fields.UUID(required=True)
    description = fields.String(load_default=None)
    currency_id = fields.UUID(required=True)
    post_date = fields.String(required=True)
    effective_date = fields.String(load_default=None)
    category_id = fields.UUID(load_default=None)
    is_cleared = fields.Boolean(load_default=False)
    splits = fields.List(fields.Nested(SplitInputSchema), required=True)


class GetTransactionsSchema(Schema):
    transaction_id = fields.UUID()


class DeleteTransactionSchema(Schema):
    transaction_id = fields.UUID(required=True)


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, '%Y-%m-%d')


def _tx_to_dict(tx, Splits, TagsOnSplits):
    splits = Splits.query.filter(Splits.tx_id == tx.id).all()
    return {
        'id': str(tx.id),
        'user_id': str(tx.user_id),
        'currency_id': str(tx.currency_id),
        'post_date': tx.post_date.isoformat() if tx.post_date else None,
        'effective_date': tx.effective_date.isoformat() if tx.effective_date else None,
        'description': tx.description,
        'category_id': str(tx.category_id) if tx.category_id else None,
        'is_cleared': tx.is_cleared,
        'splits': [
            {
                'id': str(s.id),
                'account_id': str(s.account_id),
                'quantity': float(s.quantity),
                'tag_ids': [
                    str(tos.tag_id)
                    for tos in TagsOnSplits.query.filter(TagsOnSplits.split_id == s.id).all()
                ],
            }
            for s in splits
        ],
    }


class TransactionsRoutes:
    def __init__(self, app, DB, Transactions, Splits, TagsOnSplits):
        ROUTE_PATH = f"{ROOT_PATH}/transactions"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        def get_transactions():
            try:
                data = GetTransactionsSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            if data.get('transaction_id'):
                tx = Transactions.query.filter(
                    Transactions.id == data.get('transaction_id'),
                    Transactions.user_id == get_jwt_identity()
                ).first()
                if not tx:
                    return json_response('Transaction not found', HttpCode.NOT_FOUND)
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.OK)

            txs = (Transactions.query
                   .filter(Transactions.user_id == get_jwt_identity())
                   .order_by(Transactions.post_date.desc())
                   .all())
            return json_response([_tx_to_dict(tx, Splits, TagsOnSplits) for tx in txs], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        def add_transaction():
            try:
                data = AddTransactionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)
            try:
                post_date = _parse_date(data['post_date'])
                tx = Transactions(
                    user_id=get_jwt_identity(),
                    currency_id=data['currency_id'],
                    post_date=post_date,
                    effective_date=_parse_date(data.get('effective_date')) or post_date,
                    description=data.get('description'),
                    category_id=data.get('category_id'),
                    is_cleared=data.get('is_cleared', False),
                )
                DB.session.add(tx)
                DB.session.flush()
                for split in data['splits']:
                    DB.session.add(Splits(
                        tx_id=tx.id,
                        account_id=split['account_id'],
                        quantity=split['quantity'],
                    ))
                DB.session.commit()
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        def update_transaction():
            try:
                data = UpdateTransactionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            tx = Transactions.query.filter(
                Transactions.id == data['transaction_id'],
                Transactions.user_id == get_jwt_identity()
            ).first()
            if not tx:
                return json_response('Transaction not found', HttpCode.NOT_FOUND)
            try:
                post_date = _parse_date(data['post_date'])
                tx.currency_id = data['currency_id']
                tx.post_date = post_date
                tx.effective_date = _parse_date(data.get('effective_date')) or post_date
                tx.description = data.get('description')
                tx.category_id = data.get('category_id')
                tx.is_cleared = data.get('is_cleared', False)
                Splits.query.filter(Splits.tx_id == tx.id).delete()
                for split in data['splits']:
                    DB.session.add(Splits(
                        tx_id=tx.id,
                        account_id=split['account_id'],
                        quantity=split['quantity'],
                    ))
                DB.session.commit()
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        def delete_transaction():
            try:
                data = DeleteTransactionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            tx = Transactions.query.filter(
                Transactions.id == data['transaction_id'],
                Transactions.user_id == get_jwt_identity()
            ).first()
            if not tx:
                return json_response('Transaction not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(tx)
                DB.session.commit()
                return json_response('Transaction deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
