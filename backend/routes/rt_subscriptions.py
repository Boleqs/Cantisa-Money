from marshmallow import Schema, fields, ValidationError
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response


class AddSubscriptionSchema(Schema):
    name = fields.String(required=True)
    recurrence = fields.Integer(load_default=30)
    amount = fields.Decimal(required=True, as_string=False)
    from_account_id = fields.UUID(required=True)
    to_account_id = fields.UUID(required=True)
    category_id = fields.UUID(load_default=None)


class UpdateSubscriptionSchema(Schema):
    subscription_id = fields.UUID(required=True)
    name = fields.String(required=True)
    recurrence = fields.Integer(load_default=30)
    amount = fields.Decimal(required=True, as_string=False)
    from_account_id = fields.UUID(required=True)
    to_account_id = fields.UUID(required=True)
    category_id = fields.UUID(load_default=None)


class GetSubscriptionSchema(Schema):
    subscription_id = fields.UUID()


class DeleteSubscriptionSchema(Schema):
    subscription_id = fields.UUID(required=True)


def _sub_to_dict(s):
    return {
        'id': str(s.id),
        'user_id': str(s.user_id),
        'name': s.name,
        'recurrence': s.recurrence,
        'amount': float(s.amount),
        'from_account_id': str(s.from_account_id) if s.from_account_id else None,
        'to_account_id': str(s.to_account_id) if s.to_account_id else None,
        'category_id': str(s.category_id) if s.category_id else None,
        'created_at': s.created_at.isoformat() if s.created_at else None,
        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
    }


class SubscriptionsRoutes:
    def __init__(self, app, DB, Subscriptions):
        ROUTE_PATH = f"{ROOT_PATH}/subscriptions"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        def get_subscriptions():
            try:
                data = GetSubscriptionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data.get('subscription_id'):
                s = Subscriptions.query.filter(
                    Subscriptions.id == data['subscription_id'],
                    Subscriptions.user_id == get_jwt_identity()
                ).first()
                if not s:
                    return json_response('Subscription not found', HttpCode.NOT_FOUND)
                return json_response(_sub_to_dict(s), HttpCode.OK)

            subs = (Subscriptions.query
                    .filter(Subscriptions.user_id == get_jwt_identity())
                    .order_by(Subscriptions.name)
                    .all())
            return json_response([_sub_to_dict(s) for s in subs], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        def add_subscription():
            try:
                data = AddSubscriptionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            if Subscriptions.query.filter(
                Subscriptions.user_id == get_jwt_identity(),
                Subscriptions.name == data['name']
            ).first():
                return json_response('Subscription already exists', HttpCode.CONFLICT)
            try:
                s = Subscriptions(
                    user_id=get_jwt_identity(),
                    name=data['name'],
                    recurrence=data.get('recurrence', 30),
                    amount=data['amount'],
                    from_account_id=data['from_account_id'],
                    to_account_id=data['to_account_id'],
                    category_id=data.get('category_id'),
                )
                DB.session.add(s)
                DB.session.commit()
                return json_response(_sub_to_dict(s), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        def update_subscription():
            try:
                data = UpdateSubscriptionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            s = Subscriptions.query.filter(
                Subscriptions.id == data['subscription_id'],
                Subscriptions.user_id == get_jwt_identity()
            ).first()
            if not s:
                return json_response('Subscription not found', HttpCode.NOT_FOUND)
            try:
                s.name = data['name']
                s.recurrence = data.get('recurrence', 30)
                s.amount = data['amount']
                s.from_account_id = data['from_account_id']
                s.to_account_id = data['to_account_id']
                s.category_id = data.get('category_id')
                DB.session.commit()
                return json_response(_sub_to_dict(s), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        def delete_subscription():
            try:
                data = DeleteSubscriptionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            s = Subscriptions.query.filter(
                Subscriptions.id == data['subscription_id'],
                Subscriptions.user_id == get_jwt_identity()
            ).first()
            if not s:
                return json_response('Subscription not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(s)
                DB.session.commit()
                return json_response('Subscription deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)