from datetime import datetime, date as date_cls

from flask import request
from marshmallow import Schema, fields, ValidationError, validate

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PERMISSIONS_LIST)
from backend.utils.api_responses import json_response
from backend.utils.market_price import get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission

from flask_jwt_extended import get_jwt_identity, jwt_required

COMMODITIES_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']

VALID_TYPES = ('Currency', 'Crypto')


class GetCommoditiesSchema(Schema):
    commodity_id = fields.UUID(required=False)


class AddCommoditySchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=128))
    short_name = fields.String(required=True, validate=validate.Length(min=1, max=6))
    type = fields.String(load_default='Currency', validate=validate.OneOf(VALID_TYPES))
    fraction = fields.Integer(load_default=2, validate=validate.Range(min=0, max=8))
    description = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=1024))
    track_live_rate = fields.Boolean(load_default=False)


class EditCommoditySchema(Schema):
    commodity_id = fields.UUID(required=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=128))
    short_name = fields.String(required=True, validate=validate.Length(min=1, max=6))
    type = fields.String(load_default='Currency', validate=validate.OneOf(VALID_TYPES))
    fraction = fields.Integer(load_default=2, validate=validate.Range(min=0, max=8))
    description = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=1024))
    track_live_rate = fields.Boolean(load_default=False)


class GetRateSchema(Schema):
    from_code = fields.String(required=True)
    to_code = fields.String(required=True)
    on_date = fields.Date(load_default=None)


class RefreshRateSchema(Schema):
    commodity_id = fields.UUID(required=True)


class CommoditiesRoutes:
    def __init__(self, app, DB, Users, Commodities, FxRates, UserSettings, Accounts, Transactions, Assets):
        ROUTE_PATH = f"{ROOT_PATH}/commodities"

        def _in_use(commodity_id, user_id):
            """Une devise référencée par des comptes/transactions/actifs ne doit pas pouvoir
            être supprimée : les FK sont en CASCADE, la suppression emporterait silencieusement
            tout ce qui l'utilise (comptes, transactions, actifs)."""
            return (
                Accounts.query.filter(Accounts.user_id == user_id, Accounts.currency_id == commodity_id).first()
                or Transactions.query.filter(Transactions.user_id == user_id, Transactions.currency_id == commodity_id).first()
                or Assets.query.filter(Assets.user_id == user_id, Assets.commodity_id == commodity_id).first()
            )

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, COMMODITIES_PERM)
        def get_commodities():
            try:
                data = GetCommoditiesSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            if data.get('commodity_id'):
                return json_response(Commodities.query.filter(Commodities.id == data.get('commodity_id'),
                                                     Commodities.user_id == get_jwt_identity()).first(), HttpCode.OK)
            return json_response(Commodities.query.filter(Commodities.user_id == get_jwt_identity()).all(), HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, COMMODITIES_PERM)
        def add_commodity():
            try:
                data = AddCommoditySchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            short_name = data['short_name'].strip().upper()
            if Commodities.query.filter(Commodities.user_id == user_id, Commodities.short_name == short_name).first():
                return json_response('Commodity already exists', HttpCode.CONFLICT)
            try:
                commodity = Commodities(user_id=user_id, name=data['name'], short_name=short_name,
                                        type=data['type'], fraction=data['fraction'],
                                        description=data['description'],
                                        track_live_rate=data['track_live_rate'])
                DB.session.add(commodity)
                DB.session.commit()
                return json_response('Commodity created', HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, COMMODITIES_PERM)
        def edit_commodity():
            try:
                data = EditCommoditySchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            commodity = Commodities.query.filter(Commodities.id == data['commodity_id'],
                                                 Commodities.user_id == user_id).first()
            if not commodity:
                return json_response("Commodity doesn't exist", HttpCode.NOT_FOUND)

            short_name = data['short_name'].strip().upper()
            existing = Commodities.query.filter(Commodities.user_id == user_id,
                                                Commodities.short_name == short_name,
                                                Commodities.id != data['commodity_id']).first()
            if existing:
                return json_response('Commodity already exists', HttpCode.CONFLICT)
            try:
                commodity.name = data['name']
                commodity.short_name = short_name
                commodity.type = data['type']
                commodity.fraction = data['fraction']
                commodity.description = data['description']
                commodity.track_live_rate = data['track_live_rate']
                DB.session.commit()
                return json_response('Commodity updated', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/rate", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, COMMODITIES_PERM)
        def get_rate():
            """Taux de change entre deux codes devise (cache-first, cf. backend/utils/market_price.py).
            Utilisé par le frontend pour prévisualiser la conversion d'un split inter-devises."""
            try:
                data = GetRateSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            from_code = data['from_code'].strip().upper()
            to_code = data['to_code'].strip().upper()
            rate = get_fx_rate(from_code, to_code, FxRates, on_date=data.get('on_date'))
            if rate is None:
                return json_response(f"Taux de change {from_code} → {to_code} indisponible", HttpCode.NOT_FOUND)
            return json_response({'from_code': from_code, 'to_code': to_code, 'rate': rate}, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/refresh-rate", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, COMMODITIES_PERM)
        def refresh_rate():
            """Force le rafraîchissement immédiat du taux d'une devise suivie (au lieu d'attendre
            le prochain passage du scheduler, toutes les 15 min) — sert aussi à vérifier que le
            suivi automatique fonctionne."""
            try:
                data = RefreshRateSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            commodity = Commodities.query.filter(Commodities.id == data['commodity_id'],
                                                 Commodities.user_id == user_id).first()
            if not commodity:
                return json_response("Commodity doesn't exist", HttpCode.NOT_FOUND)
            if not commodity.track_live_rate:
                return json_response("Cette devise n'est pas suivie automatiquement", HttpCode.BAD_REQUEST)

            settings = UserSettings.query.filter_by(user_id=user_id).first()
            target_currency = settings.currency if settings else 'EUR'
            if commodity.short_name == target_currency:
                return json_response(
                    f"La devise par défaut est déjà {target_currency}, rien à convertir", HttpCode.BAD_REQUEST)

            rate = get_fx_rate(commodity.short_name, target_currency, FxRates)
            if rate is None:
                return json_response(
                    f"Taux de change {commodity.short_name} → {target_currency} indisponible", HttpCode.BAD_REQUEST)
            try:
                commodity.last_rate_updated_at = datetime.now()
                DB.session.commit()
                return json_response({'rate': rate, 'target_currency': target_currency,
                                      'last_rate_updated_at': commodity.last_rate_updated_at.isoformat()}, HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, COMMODITIES_PERM)
        def delete_commodity():
            user_id = get_jwt_identity()
            commodity_id = request.args.get('commodity_id')
            commodity = Commodities.query.filter(Commodities.user_id == user_id,
                                                 Commodities.id == commodity_id).first()
            if not commodity:
                return json_response("Commodity doesn't exist", HttpCode.NOT_FOUND)
            if _in_use(commodity_id, user_id):
                return json_response('Commodity is still used by an account, a transaction or an asset', HttpCode.CONFLICT)
            try:
                DB.session.delete(commodity)
                DB.session.commit()
                return json_response('Commodity deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
