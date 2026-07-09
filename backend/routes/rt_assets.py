from datetime import datetime

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response
from backend.utils.market_price import fetch_live_price, convert_amount

VALID_ASSET_TYPES = ('Stock', 'ETF', 'RealEstate', 'Vehicle', 'Other')


class AddAssetSchema(Schema):
    symbol = fields.String(required=True)
    name = fields.String(required=True)
    asset_type = fields.String(required=True, validate=validate.OneOf(VALID_ASSET_TYPES))
    sector = fields.String(load_default=None)
    commodity_id = fields.UUID(required=True)
    value_per_unit = fields.Decimal(load_default=0, as_string=False)
    track_live_price = fields.Boolean(load_default=False)


class UpdateAssetSchema(Schema):
    asset_id = fields.UUID(required=True)
    symbol = fields.String(required=True)
    name = fields.String(required=True)
    asset_type = fields.String(required=True, validate=validate.OneOf(VALID_ASSET_TYPES))
    sector = fields.String(load_default=None)
    commodity_id = fields.UUID(required=True)
    value_per_unit = fields.Decimal(load_default=0, as_string=False)
    track_live_price = fields.Boolean(load_default=False)


class DeleteAssetSchema(Schema):
    asset_id = fields.UUID(required=True)


class RefreshAssetPriceSchema(Schema):
    asset_id = fields.UUID(required=True)


class AddPossessionSchema(Schema):
    asset_id = fields.UUID(required=True)
    account_id = fields.UUID(required=True)
    quantity = fields.Integer(required=True)
    purchase_price = fields.Decimal(required=True, as_string=False)
    purchase_date = fields.Date(required=True)


class UpdatePossessionSchema(Schema):
    possession_id = fields.UUID(required=True)
    quantity = fields.Integer(required=True)
    purchase_price = fields.Decimal(required=True, as_string=False)
    purchase_date = fields.Date(required=True)


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
        'track_live_price': a.track_live_price,
        'last_price_updated_at': a.last_price_updated_at.isoformat() if a.last_price_updated_at else None,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }


def _possession_to_dict(p):
    return {
        'id': str(p.id),
        'asset_id': str(p.asset_id),
        'account_id': str(p.account_id),
        'quantity': p.quantity,
        'purchase_price': float(p.purchase_price) if p.purchase_price is not None else None,
        'purchase_price_native': float(p.purchase_price_native) if p.purchase_price_native is not None else None,
        'purchase_date': p.purchase_date.isoformat() if p.purchase_date else None,
        'created_at': p.created_at.isoformat() if p.created_at else None,
    }


def _resolve_current_value(symbol, target_currency):
    """Récupère le prix de marché actuel du ticker et le convertit vers target_currency.
    Retourne (value_per_unit, error_response) — error_response est None si succès."""
    result = fetch_live_price(symbol)
    if not result['valid']:
        return None, json_response(result['error'], HttpCode.BAD_REQUEST)
    if result['price'] is None:
        return None, json_response(f"Prix indisponible pour '{symbol}'", HttpCode.BAD_REQUEST)

    value_per_unit = convert_amount(result['price'], result['currency'], target_currency)
    if value_per_unit is None:
        return None, json_response(
            f"Taux de change {result['currency']} → {target_currency} indisponible", HttpCode.BAD_REQUEST)
    return value_per_unit, None


def _resolve_purchase_price(symbol, target_currency, purchase_price_native, purchase_date):
    """Convertit un prix d'achat natif (devise du ticker) au taux historique de purchase_date.
    Retourne (purchase_price, error_response) — error_response est None si succès."""
    result = fetch_live_price(symbol)
    if not result['valid']:
        return None, json_response(result['error'], HttpCode.BAD_REQUEST)

    purchase_price = convert_amount(purchase_price_native, result['currency'], target_currency, on_date=purchase_date)
    if purchase_price is None:
        return None, json_response(
            f"Taux de change historique {result['currency']} → {target_currency} indisponible pour la date d'achat",
            HttpCode.BAD_REQUEST)
    return purchase_price, None


def _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, Commodities, Transactions, Splits,
                           WealthSnapshot, user_id, from_date):
    """Supprime les snapshots de patrimoine existants à partir de from_date pour cet utilisateur puis
    les reconstruit immédiatement — appelé après ajout/modification/suppression d'une position dont la
    date d'achat affecte l'historique, pour ne pas attendre le prochain cycle planifié (24h)."""
    from backend.utils.wealth import backfill_wealth_history
    from backend.scheduler import snapshot_wealth
    WealthSnapshot.query.filter(
        WealthSnapshot.user_id == user_id,
        WealthSnapshot.snapshot_date >= from_date,
    ).delete()
    DB.session.commit()
    backfill_wealth_history(DB, Accounts, Assets, AssetPossession, Commodities, Transactions, Splits, WealthSnapshot)
    snapshot_wealth(app, DB, Accounts, Assets, AssetPossession, Commodities, WealthSnapshot)


class AssetsRoutes:
    def __init__(self, app, DB, Assets, AssetPossession, Commodities, Accounts, Transactions, Splits, WealthSnapshot):
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

            if data['track_live_price']:
                commodity = Commodities.query.filter_by(id=data['commodity_id']).first()
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                value_per_unit, error = _resolve_current_value(data['symbol'], commodity.short_name)
                if error:
                    return error
                last_price_updated_at = datetime.now()
            else:
                value_per_unit = data.get('value_per_unit', 0)
                last_price_updated_at = None

            try:
                a = Assets(
                    user_id=get_jwt_identity(),
                    symbol=data['symbol'],
                    name=data['name'],
                    asset_type=data['asset_type'],
                    sector=data.get('sector'),
                    commodity_id=data['commodity_id'],
                    value_per_unit=value_per_unit,
                    track_live_price=data['track_live_price'],
                    last_price_updated_at=last_price_updated_at,
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

            if data['track_live_price']:
                commodity = Commodities.query.filter_by(id=data['commodity_id']).first()
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                value_per_unit, error = _resolve_current_value(data['symbol'], commodity.short_name)
                if error:
                    return error
                last_price_updated_at = datetime.now()
            else:
                value_per_unit = data.get('value_per_unit', 0)
                last_price_updated_at = None

            try:
                a.symbol = data['symbol']
                a.name = data['name']
                a.asset_type = data['asset_type']
                a.sector = data.get('sector')
                a.commodity_id = data['commodity_id']
                a.value_per_unit = value_per_unit
                a.track_live_price = data['track_live_price']
                a.last_price_updated_at = last_price_updated_at
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

        @app.route(f"{ROUTE_PATH}/refresh-price", methods=['POST'])
        @jwt_required()
        def refresh_asset_price():
            try:
                data = RefreshAssetPriceSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == get_jwt_identity()).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            if not a.track_live_price:
                return json_response("Cet actif n'est pas suivi en temps réel", HttpCode.BAD_REQUEST)
            commodity = Commodities.query.filter_by(id=a.commodity_id).first()
            if not commodity:
                return json_response('Commodity not found', HttpCode.NOT_FOUND)
            value_per_unit, error = _resolve_current_value(a.symbol, commodity.short_name)
            if error:
                return error
            try:
                a.value_per_unit = value_per_unit
                a.last_price_updated_at = datetime.now()
                DB.session.commit()
                return json_response(_asset_to_dict(a), HttpCode.OK)
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

            purchase_price_native = data['purchase_price']
            purchase_price = purchase_price_native
            if a.track_live_price:
                commodity = Commodities.query.filter_by(id=a.commodity_id).first()
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                purchase_price, error = _resolve_purchase_price(
                    a.symbol, commodity.short_name, purchase_price_native, data['purchase_date'])
                if error:
                    return error

            try:
                p = AssetPossession(
                    user_id=get_jwt_identity(),
                    asset_id=data['asset_id'],
                    account_id=data['account_id'],
                    quantity=data['quantity'],
                    purchase_price=purchase_price,
                    purchase_price_native=purchase_price_native,
                    purchase_date=data['purchase_date'],
                )
                DB.session.add(p)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, Commodities, Transactions, Splits,
                                       WealthSnapshot, get_jwt_identity(), data['purchase_date'])
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

            purchase_price_native = data['purchase_price']
            purchase_price = purchase_price_native
            a = Assets.query.filter_by(id=p.asset_id).first()
            if a and a.track_live_price:
                commodity = Commodities.query.filter_by(id=a.commodity_id).first()
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                purchase_price, error = _resolve_purchase_price(
                    a.symbol, commodity.short_name, purchase_price_native, data['purchase_date'])
                if error:
                    return error

            old_purchase_date = p.purchase_date.date() if p.purchase_date else None
            try:
                p.quantity = data['quantity']
                p.purchase_price = purchase_price
                p.purchase_price_native = purchase_price_native
                p.purchase_date = data['purchase_date']
                DB.session.commit()
                if old_purchase_date != data['purchase_date']:
                    from_date = min(old_purchase_date, data['purchase_date']) if old_purchase_date else data['purchase_date']
                    _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, Commodities, Transactions,
                                           Splits, WealthSnapshot, get_jwt_identity(), from_date)
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
            purchase_date = p.purchase_date.date() if p.purchase_date else None
            try:
                DB.session.delete(p)
                DB.session.commit()
                if purchase_date:
                    _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, Commodities, Transactions,
                                           Splits, WealthSnapshot, get_jwt_identity(), purchase_date)
                return json_response('Possession deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
