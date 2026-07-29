from datetime import date, timedelta

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.recurrence import next_occurrence, parse_weekdays, format_weekdays, SCHEDULE_TYPES
from backend.utils.wealth import get_dca_plan_breakdown

DCA_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']


class AddDcaPlanSchema(Schema):
    name = fields.String(required=True)
    asset_id = fields.UUID(required=True)
    source_account_id = fields.UUID(required=True)
    dest_account_id = fields.UUID(required=True)
    amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    schedule_type = fields.String(required=True, validate=validate.OneOf(SCHEDULE_TYPES))
    day_of_month = fields.Integer(load_default=None)
    month_of_year = fields.Integer(load_default=None)
    weekdays = fields.List(fields.Integer(), load_default=None)
    start_date = fields.Date(required=True)
    end_date = fields.Date(load_default=None)
    is_forecast_only = fields.Boolean(load_default=False)


class UpdateDcaPlanSchema(Schema):
    plan_id = fields.UUID(required=True)
    name = fields.String(required=True)
    asset_id = fields.UUID(required=True)
    source_account_id = fields.UUID(required=True)
    dest_account_id = fields.UUID(required=True)
    amount = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    schedule_type = fields.String(required=True, validate=validate.OneOf(SCHEDULE_TYPES))
    day_of_month = fields.Integer(load_default=None)
    month_of_year = fields.Integer(load_default=None)
    weekdays = fields.List(fields.Integer(), load_default=None)
    start_date = fields.Date(required=True)
    end_date = fields.Date(load_default=None)
    is_forecast_only = fields.Boolean(load_default=False)


class GetDcaPlanSchema(Schema):
    plan_id = fields.UUID()


class DeleteDcaPlanSchema(Schema):
    plan_id = fields.UUID(required=True)


def _dca_schedule_kwargs(data):
    """Valide la cohérence schedule_type / champs fournis. Lève ValueError si incohérent, sinon
    retourne les kwargs prêts à passer au modèle (champs non pertinents mis à None). Copie locale
    du même mécanisme que rt_subscriptions.py::_schedule_kwargs — convention du projet : schémas et
    helpers co-localisés par fichier de route, pas d'import cross-route."""
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


def _next_due(p):
    ref = p.last_executed_at.date() if p.last_executed_at else (p.start_date - timedelta(days=1))
    candidate = next_occurrence(p.schedule_type, p.day_of_month, p.month_of_year, p.weekdays, ref)
    if p.is_forecast_only:
        today = date.today()
        while candidate <= today:
            candidate = next_occurrence(p.schedule_type, p.day_of_month, p.month_of_year, p.weekdays, candidate)
    if p.end_date and candidate > p.end_date:
        return None
    return candidate


def _plan_to_dict(p, aggregates=None):
    next_due = _next_due(p)
    d = {
        'id': str(p.id),
        'user_id': str(p.user_id),
        'name': p.name,
        'asset_id': str(p.asset_id),
        'source_account_id': str(p.source_account_id),
        'dest_account_id': str(p.dest_account_id),
        'amount': float(p.amount),
        'schedule_type': p.schedule_type,
        'day_of_month': p.day_of_month,
        'month_of_year': p.month_of_year,
        'weekdays': sorted(parse_weekdays(p.weekdays)),
        'start_date': p.start_date.isoformat() if p.start_date else None,
        'end_date': p.end_date.isoformat() if p.end_date else None,
        'is_forecast_only': p.is_forecast_only,
        'last_executed_at': p.last_executed_at.isoformat() if p.last_executed_at else None,
        'next_due_at': next_due.isoformat() if next_due else None,
        'is_overdue': bool(next_due) and next_due <= date.today(),
        'is_ended': next_due is None,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'updated_at': p.updated_at.isoformat() if p.updated_at else None,
    }
    if aggregates:
        d.update(aggregates)
    return d


class DcaRoutes:
    def __init__(self, app, DB, DcaPlans, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                 Accounts, Transactions, Splits, Users, UserSettings=None):
        ROUTE_PATH = f"{ROOT_PATH}/dca"

        def _target_currency(user_id):
            settings = UserSettings.query.filter_by(user_id=user_id).first() if UserSettings else None
            return settings.currency if settings else 'EUR'

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, DCA_PERM)
        def get_dca_plans():
            try:
                data = GetDcaPlanSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            target_currency = _target_currency(user_id)

            if data.get('plan_id'):
                p = DcaPlans.query.filter(DcaPlans.id == data['plan_id'], DcaPlans.user_id == user_id).first()
                if not p:
                    return json_response('DCA plan not found', HttpCode.NOT_FOUND)
                aggregates = get_dca_plan_breakdown(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, p.id, target_currency)
                return json_response(_plan_to_dict(p, aggregates), HttpCode.OK)

            plans = DcaPlans.query.filter(DcaPlans.user_id == user_id).order_by(DcaPlans.name).all()
            result = []
            for p in plans:
                aggregates = get_dca_plan_breakdown(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, p.id, target_currency)
                result.append(_plan_to_dict(p, aggregates))
            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, DCA_PERM)
        def add_dca_plan():
            try:
                data = AddDcaPlanSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()

            if DcaPlans.query.filter(DcaPlans.user_id == user_id, DcaPlans.name == data['name']).first():
                return json_response('Un plan DCA porte déjà ce nom', HttpCode.CONFLICT)

            asset = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not asset:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            source_account = Accounts.query.filter(
                Accounts.id == data['source_account_id'], Accounts.user_id == user_id).first()
            if not source_account:
                return json_response('Source account not found', HttpCode.NOT_FOUND)
            if source_account.account_type not in ('Current', 'Assets', 'Equity'):
                return json_response(
                    "Le compte débité doit être de type 'Current', 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            dest_account = Accounts.query.filter(
                Accounts.id == data['dest_account_id'], Accounts.user_id == user_id).first()
            if not dest_account:
                return json_response('Destination account not found', HttpCode.NOT_FOUND)
            if dest_account.account_type not in ('Assets', 'Equity'):
                return json_response("Le compte de portefeuille doit être de type 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            if data.get('end_date') and data['end_date'] < data['start_date']:
                return json_response('La date de fin doit être postérieure à la date de début', HttpCode.BAD_REQUEST)

            try:
                schedule_kwargs = _dca_schedule_kwargs(data)
            except ValueError as err:
                return json_response(str(err), HttpCode.BAD_REQUEST)

            try:
                p = DcaPlans(
                    user_id=user_id,
                    name=data['name'],
                    asset_id=data['asset_id'],
                    source_account_id=data['source_account_id'],
                    dest_account_id=data['dest_account_id'],
                    amount=data['amount'],
                    start_date=data['start_date'],
                    end_date=data.get('end_date'),
                    is_forecast_only=data.get('is_forecast_only', False),
                    **schedule_kwargs,
                )
                DB.session.add(p)
                DB.session.commit()
                return json_response(_plan_to_dict(p), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, DCA_PERM)
        def update_dca_plan():
            try:
                data = UpdateDcaPlanSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()

            p = DcaPlans.query.filter(DcaPlans.id == data['plan_id'], DcaPlans.user_id == user_id).first()
            if not p:
                return json_response('DCA plan not found', HttpCode.NOT_FOUND)

            if data['name'] != p.name and DcaPlans.query.filter(
                    DcaPlans.user_id == user_id, DcaPlans.name == data['name']).first():
                return json_response('Un plan DCA porte déjà ce nom', HttpCode.CONFLICT)

            asset = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not asset:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            source_account = Accounts.query.filter(
                Accounts.id == data['source_account_id'], Accounts.user_id == user_id).first()
            if not source_account:
                return json_response('Source account not found', HttpCode.NOT_FOUND)
            if source_account.account_type not in ('Current', 'Assets', 'Equity'):
                return json_response(
                    "Le compte débité doit être de type 'Current', 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            dest_account = Accounts.query.filter(
                Accounts.id == data['dest_account_id'], Accounts.user_id == user_id).first()
            if not dest_account:
                return json_response('Destination account not found', HttpCode.NOT_FOUND)
            if dest_account.account_type not in ('Assets', 'Equity'):
                return json_response("Le compte de portefeuille doit être de type 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            if data.get('end_date') and data['end_date'] < data['start_date']:
                return json_response('La date de fin doit être postérieure à la date de début', HttpCode.BAD_REQUEST)

            try:
                schedule_kwargs = _dca_schedule_kwargs(data)
            except ValueError as err:
                return json_response(str(err), HttpCode.BAD_REQUEST)

            try:
                p.name = data['name']
                p.asset_id = data['asset_id']
                p.source_account_id = data['source_account_id']
                p.dest_account_id = data['dest_account_id']
                p.amount = data['amount']
                p.start_date = data['start_date']
                p.end_date = data.get('end_date')
                p.is_forecast_only = data.get('is_forecast_only', False)
                for key, value in schedule_kwargs.items():
                    setattr(p, key, value)
                DB.session.commit()
                return json_response(_plan_to_dict(p), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, DCA_PERM)
        def delete_dca_plan():
            try:
                data = DeleteDcaPlanSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()

            p = DcaPlans.query.filter(DcaPlans.id == data['plan_id'], DcaPlans.user_id == user_id).first()
            if not p:
                return json_response('DCA plan not found', HttpCode.NOT_FOUND)
            try:
                # Pas de garde "encore utilisé" nécessaire : dca_plan_id sur les lots existants est
                # ON DELETE SET NULL (voir migration), la traçabilité se détache proprement, les lots
                # historiques restent intacts.
                DB.session.delete(p)
                DB.session.commit()
                return json_response('DCA plan deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/execute", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, DCA_PERM)
        def execute_dca_plan():
            try:
                data = DeleteDcaPlanSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()

            p = DcaPlans.query.filter(DcaPlans.id == data['plan_id'], DcaPlans.user_id == user_id).first()
            if not p:
                return json_response('DCA plan not found', HttpCode.NOT_FOUND)

            try:
                from backend.scheduler import execute_one_dca_contribution
                success, error = execute_one_dca_contribution(
                    p, date.today(), DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits)
                if not success:
                    return json_response(error, HttpCode.BAD_REQUEST)
                aggregates = get_dca_plan_breakdown(
                    Assets, AssetPossession, AssetDisposal, Commodities, FxRates, p.id, _target_currency(user_id))
                return json_response(_plan_to_dict(p, aggregates), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
