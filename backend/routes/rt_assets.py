import uuid
from datetime import datetime, date
from decimal import Decimal

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import fetch_live_price, convert_amount, get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.portfolio_ops import resolve_current_value, resolve_purchase_price, resolve_split_amounts, format_qty

VALID_ASSET_TYPES = ('Stock', 'ETF', 'RealEstate', 'Vehicle', 'Other')
ASSETS_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']


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
    source_account_id = fields.UUID(load_default=None)
    quantity = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    purchase_price = fields.Decimal(required=True, as_string=False)
    purchase_date = fields.Date(required=True)


class UpdatePossessionSchema(Schema):
    possession_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    purchase_price = fields.Decimal(required=True, as_string=False)
    purchase_date = fields.Date(required=True)


class DeletePossessionSchema(Schema):
    possession_id = fields.UUID(required=True)


class SellPossessionSchema(Schema):
    possession_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    sale_price = fields.Decimal(required=True, as_string=False)  # devise native si track_live_price, miroir purchase_price
    sale_date = fields.Date(required=True)
    dest_account_id = fields.UUID(load_default=None)


class GetAssetHistorySchema(Schema):
    asset_id = fields.UUID(required=True)
    start_date = fields.Date(load_default=None)
    end_date = fields.Date(load_default=None)
    currency = fields.String(load_default='EUR')


class GetValuationsSchema(Schema):
    asset_id = fields.UUID(required=True)


class AddValuationSchema(Schema):
    asset_id = fields.UUID(required=True)
    valuation_date = fields.Date(required=True)
    value_per_unit = fields.Decimal(required=True, as_string=False)


class UpdateValuationSchema(Schema):
    valuation_id = fields.UUID(required=True)
    valuation_date = fields.Date(required=True)
    value_per_unit = fields.Decimal(required=True, as_string=False)


class DeleteValuationSchema(Schema):
    valuation_id = fields.UUID(required=True)


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


def _possession_to_dict(p, disposals=None):
    disposals = disposals or []
    disposed_qty = sum(d.quantity for d in disposals)
    return {
        'id': str(p.id),
        'asset_id': str(p.asset_id),
        'account_id': str(p.account_id),
        'source_account_id': str(p.source_account_id) if p.source_account_id else None,
        'tx_id': str(p.tx_id) if p.tx_id else None,
        'dca_plan_id': str(p.dca_plan_id) if p.dca_plan_id else None,
        'quantity': float(p.quantity),
        'remaining_quantity': float(p.quantity - disposed_qty),
        'purchase_price': float(p.purchase_price) if p.purchase_price is not None else None,
        'purchase_price_native': float(p.purchase_price_native) if p.purchase_price_native is not None else None,
        'purchase_date': p.purchase_date.isoformat() if p.purchase_date else None,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'disposals': [{
            'id': str(d.id), 'quantity': float(d.quantity),
            'sale_date': d.sale_date.isoformat() if d.sale_date else None,
            'realized_gain': float(d.realized_gain) if d.realized_gain is not None else None,
        } for d in disposals],
    }


def _valuation_to_dict(v):
    return {
        'id': str(v.id),
        'asset_id': str(v.asset_id),
        'valuation_date': v.valuation_date.isoformat(),
        'value_per_unit': float(v.value_per_unit),
        'created_at': v.created_at.isoformat() if v.created_at else None,
    }


def _sync_asset_value_per_unit(AssetValuations, asset):
    """Après ajout/édition/suppression d'une valorisation manuelle : Assets.value_per_unit doit
    refléter la valorisation la plus récente, puisque c'est ce champ qui sert de "valeur actuelle"
    partout ailleurs dans l'app (dashboard, breakdown du portefeuille, snapshot du jour). Si plus
    aucune valorisation n'existe, on laisse value_per_unit tel quel (comportement historique)."""
    latest = AssetValuations.query.filter_by(asset_id=asset.id).order_by(AssetValuations.valuation_date.desc()).first()
    if latest:
        asset.value_per_unit = latest.value_per_unit


def _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits,
                           WealthSnapshot, AssetValuations, user_id, from_date):
    """Supprime les snapshots de patrimoine existants à partir de from_date pour cet utilisateur puis
    les reconstruit immédiatement — appelé après ajout/modification/suppression d'une position (ou
    d'une valorisation manuelle) dont la date affecte l'historique, pour ne pas attendre le prochain
    cycle planifié (24h)."""
    from backend.utils.wealth import backfill_wealth_history
    from backend.scheduler import snapshot_wealth
    WealthSnapshot.query.filter(
        WealthSnapshot.user_id == user_id,
        WealthSnapshot.snapshot_date >= from_date,
    ).delete()
    DB.session.commit()
    backfill_wealth_history(DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations)
    snapshot_wealth(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, WealthSnapshot)


class AssetsRoutes:
    def __init__(self, app, DB, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Accounts, Transactions, Splits, WealthSnapshot, Users, AssetValuations, UserSettings):
        ROUTE_PATH = f"{ROOT_PATH}/assets"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_assets():
            user_id = get_jwt_identity()
            # `value_per_unit`/`total_value` restent dans la devise native de l'actif (nécessaire
            # pour l'édition et le calcul de plus-value par lot) ; `converted_*` est ajouté pour
            # l'affichage liste, dans la devise par défaut de l'utilisateur (cf. Dashboard/Reports
            # qui font déjà cette conversion — Portfolio.vue affichait jusqu'ici uniquement la
            # devise native, ce qui restait en USD/etc. même après changement de devise par défaut).
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            target_currency = settings.currency if settings else 'EUR'
            commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}

            assets = Assets.query.filter(Assets.user_id == user_id).order_by(Assets.name).all()
            result = []
            for a in assets:
                possessions = AssetPossession.query.filter(AssetPossession.asset_id == a.id).all()
                possession_ids = [p.id for p in possessions]
                disposals = (AssetDisposal.query.filter(AssetDisposal.possession_id.in_(possession_ids)).all()
                             if possession_ids else [])
                disposals_by_possession = {}
                for disp in disposals:
                    disposals_by_possession.setdefault(disp.possession_id, []).append(disp)

                total_qty = float(sum(p.quantity - sum(d.quantity for d in disposals_by_possession.get(p.id, []))
                                       for p in possessions))
                total_value = round(total_qty * float(a.value_per_unit or 0), 2)
                native_commodity = commodities_by_id.get(a.commodity_id)
                native_code = native_commodity.short_name if native_commodity else target_currency
                rate = 1.0 if native_code == target_currency else (get_fx_rate(native_code, target_currency, FxRates) or 1.0)
                d = _asset_to_dict(a)
                d['total_quantity'] = total_qty
                d['total_value'] = total_value
                d['display_currency'] = target_currency
                d['converted_value_per_unit'] = round(float(a.value_per_unit or 0) * rate, 4)
                d['converted_total_value'] = round(total_value * rate, 2)
                d['possessions'] = [_possession_to_dict(p, disposals_by_possession.get(p.id, [])) for p in possessions]
                result.append(d)
            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def add_asset():
            try:
                data = AddAssetSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data['track_live_price']:
                commodity = Commodities.query.filter_by(id=data['commodity_id']).first()
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                value_per_unit, error = resolve_current_value(data['symbol'], commodity.short_name, FxRates)
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
        @restricted_by_permission(Users, ASSETS_PERM)
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
                value_per_unit, error = resolve_current_value(data['symbol'], commodity.short_name, FxRates)
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
        @restricted_by_permission(Users, ASSETS_PERM)
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
        @restricted_by_permission(Users, ASSETS_PERM)
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
            value_per_unit, error = resolve_current_value(a.symbol, commodity.short_name, FxRates)
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

        # ── Historique & valorisations manuelles ────────────────────────────

        @app.route(f"{ROUTE_PATH}/history", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_asset_history():
            try:
                data = GetAssetHistorySchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            end_date = data['end_date'] or date.today()
            start_date = data['start_date']
            if not start_date:
                possessions = AssetPossession.query.filter_by(asset_id=a.id).all()
                candidates = [p.purchase_date.date() if p.purchase_date else p.created_at.date() for p in possessions]
                candidates += [v.valuation_date for v in AssetValuations.query.filter_by(asset_id=a.id).all()]
                start_date = min(candidates) if candidates else end_date

            from backend.utils.wealth import asset_value_series
            history = asset_value_series(
                Assets, AssetPossession, AssetDisposal, Commodities, FxRates, AssetValuations,
                a, start_date, end_date, data['currency'].upper())
            return json_response(history, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_valuations():
            try:
                data = GetValuationsSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            valuations = AssetValuations.query.filter_by(asset_id=a.id).order_by(AssetValuations.valuation_date).all()
            return json_response([_valuation_to_dict(v) for v in valuations], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def add_valuation():
            try:
                data = AddValuationSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            if a.track_live_price:
                return json_response("Cet actif suit un cours live, pas de saisie manuelle possible", HttpCode.BAD_REQUEST)
            if AssetValuations.query.filter_by(asset_id=a.id, valuation_date=data['valuation_date']).first():
                return json_response('Une valorisation existe déjà à cette date', HttpCode.CONFLICT)
            try:
                v = AssetValuations(
                    user_id=user_id,
                    asset_id=a.id,
                    valuation_date=data['valuation_date'],
                    value_per_unit=data['value_per_unit'],
                )
                DB.session.add(v)
                DB.session.flush()
                _sync_asset_value_per_unit(AssetValuations, a)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                       Splits, WealthSnapshot, AssetValuations, user_id, data['valuation_date'])
                return json_response(_valuation_to_dict(v), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def update_valuation():
            try:
                data = UpdateValuationSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            v = AssetValuations.query.filter(
                AssetValuations.id == data['valuation_id'], AssetValuations.user_id == user_id).first()
            if not v:
                return json_response('Valuation not found', HttpCode.NOT_FOUND)
            a = Assets.query.filter_by(id=v.asset_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            if data['valuation_date'] != v.valuation_date and AssetValuations.query.filter_by(
                    asset_id=v.asset_id, valuation_date=data['valuation_date']).first():
                return json_response('Une valorisation existe déjà à cette date', HttpCode.CONFLICT)

            old_date = v.valuation_date
            try:
                v.valuation_date = data['valuation_date']
                v.value_per_unit = data['value_per_unit']
                DB.session.flush()
                _sync_asset_value_per_unit(AssetValuations, a)
                DB.session.commit()
                from_date = min(old_date, data['valuation_date'])
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                       Splits, WealthSnapshot, AssetValuations, user_id, from_date)
                return json_response(_valuation_to_dict(v), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def delete_valuation():
            try:
                data = DeleteValuationSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            v = AssetValuations.query.filter(
                AssetValuations.id == data['valuation_id'], AssetValuations.user_id == user_id).first()
            if not v:
                return json_response('Valuation not found', HttpCode.NOT_FOUND)
            a = Assets.query.filter_by(id=v.asset_id).first()
            valuation_date = v.valuation_date
            try:
                DB.session.delete(v)
                DB.session.flush()
                if a:
                    _sync_asset_value_per_unit(AssetValuations, a)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                       Splits, WealthSnapshot, AssetValuations, user_id, valuation_date)
                return json_response('Valuation deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        # ── Possessions ──────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/possessions", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def add_possession():
            try:
                data = AddPossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            dest_account = Accounts.query.filter(Accounts.id == data['account_id'], Accounts.user_id == user_id).first()
            if not dest_account:
                return json_response('Account not found', HttpCode.NOT_FOUND)
            if dest_account.account_type not in ('Assets', 'Equity'):
                return json_response("Le compte doit être de type 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            source_account_id = data.get('source_account_id')
            source_account = None
            if source_account_id:
                source_account = Accounts.query.filter(
                    Accounts.id == source_account_id, Accounts.user_id == user_id).first()
                if not source_account:
                    return json_response('Source account not found', HttpCode.NOT_FOUND)
                if source_account.account_type not in ('Current', 'Assets', 'Equity'):
                    return json_response(
                        "Le compte débité doit être de type 'Current', 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            commodity = Commodities.query.filter_by(id=a.commodity_id).first()
            if not commodity:
                return json_response('Commodity not found', HttpCode.NOT_FOUND)

            purchase_price_native = data['purchase_price']
            purchase_price = purchase_price_native
            if a.track_live_price:
                purchase_price, error = resolve_purchase_price(
                    a.symbol, commodity.short_name, purchase_price_native, data['purchase_date'], FxRates)
                if error:
                    return error

            dest_amount = source_amount = dest_fx_rate = None
            if source_account:
                total_cost = float(data['quantity']) * float(purchase_price)
                dest_amount, source_amount, dest_fx_rate, error = resolve_split_amounts(
                    Accounts, Commodities, dest_account, source_account, total_cost,
                    commodity.short_name, data['purchase_date'], FxRates)
                if error:
                    return error

            try:
                tx = None
                source_split_id = dest_split_id = None
                if source_account:
                    tx = Transactions(
                        user_id=user_id,
                        currency_id=source_account.currency_id,
                        post_date=data['purchase_date'],
                        effective_date=data['purchase_date'],
                        description=f"Achat {a.symbol} x{format_qty(data['quantity'])}",
                        category_id=None,
                        is_cleared=True,
                    )
                    DB.session.add(tx)
                    DB.session.flush()
                    # Ids générés explicitement (pas de lookup par account_id à la modification —
                    # ambigu quand source_account == dest_account, cf. achat autofinancé par le CTO).
                    source_split_id, dest_split_id = uuid.uuid4(), uuid.uuid4()
                    DB.session.add(Splits(id=source_split_id, tx_id=tx.id, account_id=source_account.id, quantity=-source_amount, fx_rate=1.0))
                    DB.session.add(Splits(id=dest_split_id, tx_id=tx.id, account_id=dest_account.id, quantity=dest_amount, fx_rate=dest_fx_rate))
                    DB.session.flush()

                p = AssetPossession(
                    user_id=user_id,
                    asset_id=data['asset_id'],
                    account_id=data['account_id'],
                    source_account_id=source_account_id,
                    tx_id=tx.id if tx else None,
                    source_split_id=source_split_id,
                    dest_split_id=dest_split_id,
                    quantity=data['quantity'],
                    purchase_price=purchase_price,
                    purchase_price_native=purchase_price_native,
                    purchase_date=data['purchase_date'],
                )
                DB.session.add(p)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits,
                                       WealthSnapshot, AssetValuations, user_id, data['purchase_date'])
                return json_response(_possession_to_dict(p), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def update_possession():
            try:
                data = UpdatePossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            p = AssetPossession.query.filter(
                AssetPossession.id == data['possession_id'],
                AssetPossession.user_id == user_id
            ).first()
            if not p:
                return json_response('Possession not found', HttpCode.NOT_FOUND)

            existing_disposals = AssetDisposal.query.filter_by(possession_id=p.id).all()
            sold_qty = sum(disp.quantity for disp in existing_disposals)
            if data['quantity'] < sold_qty:
                return json_response(
                    f"Impossible de réduire la quantité en dessous de {sold_qty} "
                    f"(déjà cédée via {len(existing_disposals)} vente(s))",
                    HttpCode.BAD_REQUEST)

            purchase_price_native = data['purchase_price']
            purchase_price = purchase_price_native
            a = Assets.query.filter_by(id=p.asset_id).first()
            commodity = Commodities.query.filter_by(id=a.commodity_id).first() if a else None
            if a and a.track_live_price:
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                purchase_price, error = resolve_purchase_price(
                    a.symbol, commodity.short_name, purchase_price_native, data['purchase_date'], FxRates)
                if error:
                    return error

            dest_amount = source_amount = dest_fx_rate = None
            if p.tx_id and p.source_account_id and commodity:
                dest_account = Accounts.query.filter_by(id=p.account_id).first()
                source_account = Accounts.query.filter_by(id=p.source_account_id).first()
                total_cost = float(data['quantity']) * float(purchase_price)
                dest_amount, source_amount, dest_fx_rate, error = resolve_split_amounts(
                    Accounts, Commodities, dest_account, source_account, total_cost,
                    commodity.short_name, data['purchase_date'], FxRates)
                if error:
                    return error

            old_purchase_date = p.purchase_date.date() if p.purchase_date else None
            try:
                p.quantity = data['quantity']
                p.purchase_price = purchase_price
                p.purchase_price_native = purchase_price_native
                p.purchase_date = data['purchase_date']

                if p.tx_id and dest_amount is not None:
                    tx = Transactions.query.filter_by(id=p.tx_id).first()
                    if tx:
                        tx.post_date = data['purchase_date']
                        tx.effective_date = data['purchase_date']
                        tx.description = f"Achat {a.symbol} x{format_qty(data['quantity'])}"
                    source_split = Splits.query.filter_by(id=p.source_split_id).first()
                    dest_split = Splits.query.filter_by(id=p.dest_split_id).first()
                    if source_split:
                        source_split.quantity = -source_amount
                    if dest_split:
                        dest_split.quantity = dest_amount
                        dest_split.fx_rate = dest_fx_rate

                DB.session.commit()
                if old_purchase_date != data['purchase_date']:
                    from_date = min(old_purchase_date, data['purchase_date']) if old_purchase_date else data['purchase_date']
                    _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                           Splits, WealthSnapshot, AssetValuations, user_id, from_date)
                return json_response(_possession_to_dict(p, existing_disposals), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def delete_possession():
            try:
                data = DeletePossessionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            p = AssetPossession.query.filter(
                AssetPossession.id == data['possession_id'],
                AssetPossession.user_id == user_id
            ).first()
            if not p:
                return json_response('Possession not found', HttpCode.NOT_FOUND)
            if AssetDisposal.query.filter_by(possession_id=p.id).first():
                return json_response('Possession is still used by one or more disposals (sales)', HttpCode.CONFLICT)
            purchase_date = p.purchase_date.date() if p.purchase_date else None
            tx_id = p.tx_id
            try:
                DB.session.delete(p)
                if tx_id:
                    tx = Transactions.query.filter_by(id=tx_id).first()
                    if tx:
                        DB.session.delete(tx)  # cascade supprime les Splits liés (splits.py: ondelete='CASCADE')
                DB.session.commit()
                if purchase_date:
                    _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                           Splits, WealthSnapshot, AssetValuations, user_id, purchase_date)
                return json_response('Possession deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions/sell", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def sell_possession():
            try:
                data = SellPossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            p = AssetPossession.query.filter(
                AssetPossession.id == data['possession_id'],
                AssetPossession.user_id == user_id
            ).first()
            if not p:
                return json_response('Possession not found', HttpCode.NOT_FOUND)

            existing_disposals = AssetDisposal.query.filter_by(possession_id=p.id).all()
            already_sold = sum(disp.quantity for disp in existing_disposals)
            remaining = p.quantity - already_sold
            if data['quantity'] > remaining:
                return json_response(
                    f"Quantité vendue ({data['quantity']}) supérieure à la quantité restante du lot ({remaining})",
                    HttpCode.BAD_REQUEST)

            a = Assets.query.filter_by(id=p.asset_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            commodity = Commodities.query.filter_by(id=a.commodity_id).first()
            if not commodity:
                return json_response('Commodity not found', HttpCode.NOT_FOUND)

            sale_price_native = data['sale_price']
            sale_price = sale_price_native
            if a.track_live_price:
                sale_price, error = resolve_purchase_price(
                    a.symbol, commodity.short_name, sale_price_native, data['sale_date'], FxRates)
                if error:
                    return error

            position_account = Accounts.query.filter_by(id=p.account_id).first()
            dest_account_id = data.get('dest_account_id')
            dest_account = None
            if dest_account_id:
                dest_account = Accounts.query.filter(
                    Accounts.id == dest_account_id, Accounts.user_id == user_id).first()
                if not dest_account:
                    return json_response('Destination account not found', HttpCode.NOT_FOUND)
                if dest_account.account_type not in ('Current', 'Assets', 'Equity'):
                    return json_response(
                        "Le compte crédité doit être de type 'Current', 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            dest_amount = source_amount = dest_fx_rate = None
            if dest_account:
                total_proceeds = float(data['quantity']) * float(sale_price)
                # Rôles inversés par rapport à add_possession : ici "dest_account" est le compte
                # crédité (le cash qui entre), "source_account" est le compte débité (la position
                # qui sort) — cf. décision de conception Phase 2 (vente = renversement à 2 splits,
                # au montant de la vente, pas au coût d'achat).
                dest_amount, source_amount, dest_fx_rate, error = resolve_split_amounts(
                    Accounts, Commodities, dest_account, position_account, total_proceeds,
                    commodity.short_name, data['sale_date'], FxRates)
                if error:
                    return error

            realized_gain = None
            if p.purchase_price is not None:
                realized_gain = (float(sale_price) - float(p.purchase_price)) * float(data['quantity'])

            holding_period_days = None
            if p.purchase_date:
                purchase_date_only = p.purchase_date.date() if hasattr(p.purchase_date, 'date') else p.purchase_date
                holding_period_days = (data['sale_date'] - purchase_date_only).days

            try:
                tx = None
                source_split_id = dest_split_id = None
                if dest_account:
                    tx = Transactions(
                        user_id=user_id,
                        currency_id=position_account.currency_id,
                        post_date=data['sale_date'],
                        effective_date=data['sale_date'],
                        description=f"Vente {a.symbol} x{format_qty(data['quantity'])}",
                        category_id=None,
                        is_cleared=True,
                    )
                    DB.session.add(tx)
                    DB.session.flush()
                    source_split_id, dest_split_id = uuid.uuid4(), uuid.uuid4()
                    # source = compte de la position (débité, les titres "sortent") ; dest = compte
                    # crédité (le cash entre) — voir commentaire ci-dessus sur l'inversion des rôles.
                    DB.session.add(Splits(id=source_split_id, tx_id=tx.id, account_id=position_account.id, quantity=-source_amount, fx_rate=1.0))
                    DB.session.add(Splits(id=dest_split_id, tx_id=tx.id, account_id=dest_account.id, quantity=dest_amount, fx_rate=dest_fx_rate))
                    DB.session.flush()

                disposal = AssetDisposal(
                    user_id=user_id,
                    possession_id=p.id,
                    quantity=data['quantity'],
                    sale_price=sale_price,
                    sale_price_native=sale_price_native,
                    sale_date=data['sale_date'],
                    dest_account_id=dest_account_id,
                    tx_id=tx.id if tx else None,
                    source_split_id=source_split_id,
                    dest_split_id=dest_split_id,
                    realized_gain=realized_gain,
                    holding_period_days=holding_period_days,
                )
                DB.session.add(disposal)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                                       Transactions, Splits, WealthSnapshot, AssetValuations, user_id, data['sale_date'])
                return json_response(_possession_to_dict(p, existing_disposals + [disposal]), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
