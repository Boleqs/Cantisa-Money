from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response

VALID_ASSET_TYPES = ('Stock', 'ETF', 'RealEstate', 'Vehicle', 'Other')


class AddAssetSchema(Schema):
    symbol = fields.String(required=True)
    name = fields.String(required=True)
    asset_type = fields.String(required=True, validate=validate.OneOf(VALID_ASSET_TYPES))
    sector = fields.String(load_default=None)
    commodity_id = fields.UUID(required=True)
    value_per_unit = fields.Decimal(load_default=0, as_string=False)


class UpdateAssetSchema(Schema):
    asset_id = fields.UUID(required=True)
    symbol = fields.String(required=True)
    name = fields.String(required=True)
    asset_type = fields.String(required=True, validate=validate.OneOf(VALID_ASSET_TYPES))
    sector = fields.String(load_default=None)
    commodity_id = fields.UUID(required=True)
    value_per_unit = fields.Decimal(load_default=0, as_string=False)


class DeleteAssetSchema(Schema):
    asset_id = fields.UUID(required=True)


class AddPossessionSchema(Schema):
    asset_id = fields.UUID(required=True)
    account_id = fields.UUID(required=True)
    quantity = fields.Integer(required=True)


class UpdatePossessionSchema(Schema):
    possession_id = fields.UUID(required=True)
    quantity = fields.Integer(required=True)


class DeletePossessionSchema(Schema):
    possession_id = fields.UUID(required=True)


def _asset_to_dict(a):
    return {
        'id': str(a.id),
        'symbol': a.symbol,
        'name': a.name,
        'asset_type': a.asset_type,
        'sector': a.sector,
        'commodity_id': str(a.commodity_id),
        'value_per_unit': float(a.value_per_unit or 0),
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }


def _possession_to_dict(p):
    return {
        'id': str(p.id),
        'asset_id': str(p.asset_id),
        'account_id': str(p.account_id),
        'quantity': p.quantity,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


class AssetsRoutes:
    def __init__(self, app, DB, Assets, AssetPossession):
        ROUTE_PATH = f"{ROOT_PATH}/assets"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        def get_assets():
            user_id = get_jwt_identity()
            assets = Assets.query.filter(Assets.user_id == user_id).order_by(Assets.name).all()
            result = []
            for a in assets:
                possessions = AssetPossession.query.filter(AssetPossession.asset_id == a.id).all()
                total_qty = sum(p.quantity for p in possessions)
                total_value = round(total_qty * float(a.value_per_unit or 0), 2)
                d = _asset_to_dict(a)
                d['total_quantity'] = total_qty
                d['total_value'] = total_value
                d['possessions'] = [_possession_to_dict(p) for p in possessions]
                result.append(d)
            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        def add_asset():
            try:
                data = AddAssetSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            try:
                a = Assets(
                    user_id=get_jwt_identity(),
                    symbol=data['symbol'],
                    name=data['name'],
                    asset_type=data['asset_type'],
                    sector=data.get('sector'),
                    commodity_id=data['commodity_id'],
                    value_per_unit=data.get('value_per_unit', 0),
                )
                DB.session.add(a)
                DB.session.commit()
                return json_response(_asset_to_dict(a), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        def update_asset():
            try:
                data = UpdateAssetSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == get_jwt_identity()).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            try:
                a.symbol = data['symbol']
                a.name = data['name']
                a.asset_type = data['asset_type']
                a.sector = data.get('sector')
                a.commodity_id = data['commodity_id']
                a.value_per_unit = data.get('value_per_unit', 0)
                DB.session.commit()
                return json_response(_asset_to_dict(a), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        def delete_asset():
            try:
                data = DeleteAssetSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == get_jwt_identity()).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(a)
                DB.session.commit()
                return json_response('Asset deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        # ── Possessions ──────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/possessions", methods=['POST'])
        @jwt_required()
        def add_possession():
            try:
                data = AddPossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == get_jwt_identity()).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            try:
                p = AssetPossession(
                    user_id=get_jwt_identity(),
                    asset_id=data['asset_id'],
                    account_id=data['account_id'],
                    quantity=data['quantity'],
                )
                DB.session.add(p)
                DB.session.commit()
                return json_response(_possession_to_dict(p), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions", methods=['PATCH'])
        @jwt_required()
        def update_possession():
            try:
                data = UpdatePossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            p = AssetPossession.query.filter(
                AssetPossession.id == data['possession_id'],
                AssetPossession.user_id == get_jwt_identity()
            ).first()
            if not p:
                return json_response('Possession not found', HttpCode.NOT_FOUND)
            try:
                p.quantity = data['quantity']
                DB.session.commit()
                return json_response(_possession_to_dict(p), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions", methods=['DELETE'])
        @jwt_required()
        def delete_possession():
            try:
                data = DeletePossessionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            p = AssetPossession.query.filter(
                AssetPossession.id == data['possession_id'],
                AssetPossession.user_id == get_jwt_identity()
            ).first()
            if not p:
                return json_response('Possession not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(p)
                DB.session.commit()
                return json_response('Possession deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
