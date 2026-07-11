from datetime import date

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import convert_amount
from backend.utils.wealth import compute_bank_net_worth, get_portfolio_breakdown, _portfolio_account_ids
from backend.utils.restricted_by_permission import restricted_by_permission

WEALTH_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']

BANK_TYPE_LABELS = {
    'Current': 'Liquidités',
    'Assets': 'Épargne / autres comptes',
    'Equity': 'Comptes Equity / PEA',
}
PORTFOLIO_TYPE_LABELS = {
    'Stock': 'Actions',
    'ETF': 'ETF',
    'RealEstate': 'Immobilier',
    'Vehicle': 'Véhicules',
    'Other': 'Autres actifs',
}


def _bank_allocation(Accounts, Commodities, AssetPossession, FxRates, user_id, target_currency):
    accounts = Accounts.query.filter(
        Accounts.user_id == user_id,
        Accounts.account_type.in_(BANK_TYPE_LABELS.keys()),
        ~Accounts.id.in_(_portfolio_account_ids(AssetPossession, user_id))
    ).all()
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}
    totals = {}
    for a in accounts:
        balance = float(a.total_earned or 0) - float(a.total_spent or 0)
        commodity = commodities_by_id.get(a.currency_id)
        code = commodity.short_name if commodity else target_currency
        converted = convert_amount(balance, code, target_currency, FxRates) or 0
        label = BANK_TYPE_LABELS[a.account_type]
        totals[label] = totals.get(label, 0) + converted
    return [{'label': label, 'value': round(v, 2)} for label, v in totals.items() if v]


def _portfolio_allocation(portfolio):
    totals = {}
    for a in portfolio:
        label = PORTFOLIO_TYPE_LABELS.get(a['asset_type'], a['asset_type'])
        totals[label] = totals.get(label, 0) + a['value']
    return [{'label': label, 'value': round(v, 2)} for label, v in totals.items() if v]


def _currency_allocation(Accounts, Commodities, AssetPossession, FxRates, user_id, portfolio, target_currency):
    accounts = Accounts.query.filter(
        Accounts.user_id == user_id,
        Accounts.account_type.in_(('Current', 'Assets', 'Equity')),
        ~Accounts.id.in_(_portfolio_account_ids(AssetPossession, user_id))
    ).all()
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}
    totals = {}
    for a in accounts:
        balance = float(a.total_earned or 0) - float(a.total_spent or 0)
        commodity = commodities_by_id.get(a.currency_id)
        code = commodity.short_name if commodity else target_currency
        totals[code] = totals.get(code, 0) + (convert_amount(balance, code, target_currency, FxRates) or 0)
    for a in portfolio:
        totals[a['currency']] = totals.get(a['currency'], 0) + a['value']
    return [{'currency': code, 'value': round(v, 2)} for code, v in totals.items() if v]


def _sector_allocation(portfolio):
    totals = {}
    for a in portfolio:
        if a['asset_type'] not in ('Stock', 'ETF') or not a['sector']:
            continue
        totals[a['sector']] = totals.get(a['sector'], 0) + a['value']
    return [{'sector': s, 'value': round(v, 2)} for s, v in totals.items() if v]


class WealthRoutes:
    def __init__(self, app, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, WealthSnapshot, Users):
        ROUTE_PATH = f"{ROOT_PATH}/wealth"

        @app.route(f"{ROUTE_PATH}/overview", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, WEALTH_PERM)
        def get_wealth_overview():
            currency = request.args.get('currency', 'EUR').upper()
            user_id = get_jwt_identity()

            bank_net_worth = compute_bank_net_worth(Accounts, Commodities, AssetPossession, FxRates, user_id, currency)
            portfolio = get_portfolio_breakdown(Assets, AssetPossession, Commodities, FxRates, user_id, currency)
            portfolio_value = round(sum(a['value'] for a in portfolio), 2)

            gains = [a for a in portfolio if a['gain_abs'] is not None]
            unrealized_gain = round(sum(a['gain_abs'] for a in gains), 2)
            invested = sum(a['purchase_value'] for a in gains)
            unrealized_gain_pct = round(unrealized_gain / invested * 100, 2) if invested else None

            allocation_by_type = _bank_allocation(Accounts, Commodities, AssetPossession, FxRates, user_id, currency) + _portfolio_allocation(portfolio)
            allocation_by_currency = _currency_allocation(Accounts, Commodities, AssetPossession, FxRates, user_id, portfolio, currency)
            allocation_by_sector = _sector_allocation(portfolio)

            top_movers = sorted(
                [a for a in gains if (a['gain_pct'] or 0) > 0],
                key=lambda a: a['gain_pct'], reverse=True
            )[:5]
            worst_movers = sorted(
                [a for a in gains if (a['gain_pct'] or 0) < 0],
                key=lambda a: a['gain_pct']
            )[:5]

            return json_response({
                'currency': currency,
                'kpis': {
                    'net_worth_total': round(bank_net_worth + portfolio_value, 2),
                    'bank_net_worth': bank_net_worth,
                    'portfolio_value': portfolio_value,
                    'unrealized_gain': unrealized_gain,
                    'unrealized_gain_pct': unrealized_gain_pct,
                },
                'allocation_by_type': allocation_by_type,
                'allocation_by_currency': allocation_by_currency,
                'allocation_by_sector': allocation_by_sector,
                'top_movers': top_movers,
                'worst_movers': worst_movers,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/history", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, WEALTH_PERM)
        def get_wealth_history():
            currency = request.args.get('currency', 'EUR').upper()
            user_id = get_jwt_identity()
            query = WealthSnapshot.query.filter_by(user_id=user_id)

            start_str = request.args.get('start_date')
            end_str = request.args.get('end_date')
            try:
                if start_str:
                    query = query.filter(WealthSnapshot.snapshot_date >= date.fromisoformat(start_str))
                if end_str:
                    query = query.filter(WealthSnapshot.snapshot_date <= date.fromisoformat(end_str))
            except ValueError:
                return json_response('Invalid date format (YYYY-MM-DD expected)', HttpCode.BAD_REQUEST)

            snapshots = query.order_by(WealthSnapshot.snapshot_date).all()

            history = []
            for s in snapshots:
                total = float(s.total)
                bank = float(s.bank_net_worth)
                portfolio = float(s.portfolio_value)
                if currency != 'EUR':
                    total = convert_amount(total, 'EUR', currency, FxRates, on_date=s.snapshot_date) or total
                    bank = convert_amount(bank, 'EUR', currency, FxRates, on_date=s.snapshot_date) or bank
                    portfolio = convert_amount(portfolio, 'EUR', currency, FxRates, on_date=s.snapshot_date) or portfolio
                history.append({
                    'date': s.snapshot_date.isoformat(),
                    'total': round(total, 2),
                    'bank_net_worth': round(bank, 2),
                    'portfolio_value': round(portfolio, 2),
                })

            return json_response(history, HttpCode.OK)
