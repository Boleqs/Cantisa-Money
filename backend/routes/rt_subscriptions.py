from datetime import date

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.recurrence import next_occurrence, parse_weekdays, format_weekdays, SCHEDULE_TYPES

SUBSCRIPTIONS_PERM = VAR_PERMISSIONS_LIST['Planification']['id']


class AddSubscriptionSchema(Schema):
    name = fields.String(required=True)
    schedule_type = fields.String(required=True, validate=validate.OneOf(SCHEDULE_TYPES))
    day_of_month = fields.Integer(load_default=None)
    month_of_year = fields.Integer(load_default=None)
    weekdays = fields.List(fields.Integer(), load_default=None)
    amount = fields.Decimal(required=True, as_string=False)
    from_account_id = fields.UUID(required=True)
    to_account_id = fields.UUID(required=True)
    category_id = fields.UUID(load_default=None)
    is_forecast_only = fields.Boolean(load_default=False)


class UpdateSubscriptionSchema(Schema):
    subscription_id = fields.UUID(required=True)
    name = fields.String(required=True)
    schedule_type = fields.String(required=True, validate=validate.OneOf(SCHEDULE_TYPES))
    day_of_month = fields.Integer(load_default=None)
    month_of_year = fields.Integer(load_default=None)
    weekdays = fields.List(fields.Integer(), load_default=None)
    amount = fields.Decimal(required=True, as_string=False)
    from_account_id = fields.UUID(required=True)
    to_account_id = fields.UUID(required=True)
    category_id = fields.UUID(load_default=None)
    is_forecast_only = fields.Boolean(load_default=False)


class GetSubscriptionSchema(Schema):
    subscription_id = fields.UUID()


class DeleteSubscriptionSchema(Schema):
    subscription_id = fields.UUID(required=True)


def _schedule_kwargs(data):
    """Valide la cohérence schedule_type / champs fournis. Lève ValueError si incohérent,
    sinon retourne les kwargs prêts à passer au modèle (champs non pertinents mis à None)."""
    schedule_type = data['schedule_type']
    day_of_month = data.get('day_of_month')
    month_of_year = data.get('month_of_year')
    weekdays = data.get('weekdays') or []

    if schedule_type in ('monthly', 'yearly') and not (day_of_month and 1 <= day_of_month <= 31):
        raise ValueError("day_of_month requis (1-31) pour une planification mensuelle ou annuelle")
    if schedule_type == 'yearly' and not (month_of_year and 1 <= month_of_year <= 12):
        raise ValueError("month_of_year requis (1-12) pour une planification annuelle")
    if schedule_type == 'weekly' and (not weekdays or any(not (1 <= w <= 7) for w in weekdays)):
        raise ValueError("weekdays requis (1=lundi … 7=dimanche) pour une planification hebdomadaire")

    return {
        'schedule_type': schedule_type,
        'day_of_month': day_of_month if schedule_type in ('monthly', 'yearly') else None,
        'month_of_year': month_of_year if schedule_type == 'yearly' else None,
        'weekdays': format_weekdays(weekdays) if schedule_type == 'weekly' else None,
    }


def _next_due(s):
    ref = s.last_executed_at.date() if s.last_executed_at else s.created_at.date()
    candidate = next_occurrence(s.schedule_type, s.day_of_month, s.month_of_year, s.weekdays, ref)
    if s.is_forecast_only:
        # Jamais exécuté par le scheduler -> last_executed_at ne se met jamais à jour tout
        # seul. Sans ça l'échéance resterait bloquée dans le passé indéfiniment : on avance
        # ici jusqu'à la prochaine échéance future, sans toucher last_executed_at (pur calcul
        # d'affichage, pas d'état persisté).
        today = date.today()
        while candidate <= today:
            candidate = next_occurrence(s.schedule_type, s.day_of_month, s.month_of_year, s.weekdays, candidate)
    return candidate


def _sub_to_dict(s):
    next_due = _next_due(s)
    return {
        'id': str(s.id),
        'user_id': str(s.user_id),
        'name': s.name,
        'schedule_type': s.schedule_type,
        'day_of_month': s.day_of_month,
        'month_of_year': s.month_of_year,
        'weekdays': sorted(parse_weekdays(s.weekdays)),
        'amount': float(s.amount),
        'from_account_id': str(s.from_account_id) if s.from_account_id else None,
        'to_account_id': str(s.to_account_id) if s.to_account_id else None,
        'category_id': str(s.category_id) if s.category_id else None,
        'is_forecast_only': s.is_forecast_only,
        'last_executed_at': s.last_executed_at.isoformat() if s.last_executed_at else None,
        'next_due_at': next_due.isoformat(),
        'is_overdue': next_due <= date.today(),
        'created_at': s.created_at.isoformat() if s.created_at else None,
        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
    }


class SubscriptionsRoutes:
    def __init__(self, app, DB, Subscriptions, Users, Transactions=None, Splits=None, Accounts=None):
        ROUTE_PATH = f"{ROOT_PATH}/subscriptions"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, SUBSCRIPTIONS_PERM)
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
        @restricted_by_permission(Users, SUBSCRIPTIONS_PERM)
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
                schedule_kwargs = _schedule_kwargs(data)
            except ValueError as err:
                return json_response(str(err), HttpCode.BAD_REQUEST)
            try:
                s = Subscriptions(
                    user_id=get_jwt_identity(),
                    name=data['name'],
                    amount=data['amount'],
                    from_account_id=data['from_account_id'],
                    to_account_id=data['to_account_id'],
                    category_id=data.get('category_id'),
                    is_forecast_only=data.get('is_forecast_only', False),
                    **schedule_kwargs,
                )
                DB.session.add(s)
                DB.session.commit()
                return json_response(_sub_to_dict(s), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, SUBSCRIPTIONS_PERM)
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
                schedule_kwargs = _schedule_kwargs(data)
            except ValueError as err:
                return json_response(str(err), HttpCode.BAD_REQUEST)
            try:
                s.name = data['name']
                s.amount = data['amount']
                s.from_account_id = data['from_account_id']
                s.to_account_id = data['to_account_id']
                s.category_id = data.get('category_id')
                s.is_forecast_only = data.get('is_forecast_only', False)
                for key, value in schedule_kwargs.items():
                    setattr(s, key, value)
                DB.session.commit()
                return json_response(_sub_to_dict(s), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, SUBSCRIPTIONS_PERM)
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

        @app.route(f"{ROUTE_PATH}/execute", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, SUBSCRIPTIONS_PERM)
        def execute_subscription():
            if not Transactions or not Splits or not Accounts:
                return json_response('Scheduler non configuré', HttpCode.SERVER_ERROR)
            try:
                data = DeleteSubscriptionSchema().load(request.json or {})
            except Exception as err:
                return json_response(str(err), HttpCode.BAD_REQUEST)

            s = Subscriptions.query.filter(
                Subscriptions.id == data['subscription_id'],
                Subscriptions.user_id == get_jwt_identity()
            ).first()
            if not s:
                return json_response('Subscription not found', HttpCode.NOT_FOUND)

            try:
                from backend.scheduler import execute_one_subscription
                execute_one_subscription(s, date.today(), DB, Transactions, Splits, Accounts)
                return json_response(_sub_to_dict(s), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
