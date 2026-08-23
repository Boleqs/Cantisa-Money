from datetime import date

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import convert_amount
from backend.utils.wealth import (compute_bank_net_worth, compute_total_liabilities, get_portfolio_breakdown,
                                  get_portfolio_container_account_values, _portfolio_account_ids)
from backend.utils.restricted_by_permission import restricted_by_permission

WEALTH_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']

PORTFOLIO_TYPE_LABELS = {
    'Stock': 'Actions',
    'ETF': 'ETF',
    'RealEstate': 'Immobilier',
    'Vehicle': 'Véhicules',
    'Other': 'Autres actifs',
}


def _portfolio_allocation(portfolio):
    totals = {}
    for a in portfolio:
        label = PORTFOLIO_TYPE_LABELS.get(a['asset_type'], a['asset_type'])
        totals[label] = totals.get(label, 0) + a['value']
    return [{'label': label, 'value': round(v, 2)} for label, v in totals.items() if v]


def _currency_allocation(portfolio):
    """Répartition du portefeuille par devise — volontairement sans les comptes bancaires (Current/
    Assets/Equity) : la page Patrimoine (Gestion financière) ne concerne que les actifs et passifs,
    voir la note sur le périmètre du Patrimoine dans get_wealth_overview()."""
    totals = {}
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
    def __init__(self, app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                 WealthSnapshot, Users, Splits=None):
        ROUTE_PATH = f"{ROOT_PATH}/wealth"

        @app.route(f"{ROUTE_PATH}/account-values", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, WEALTH_PERM)
        def get_account_values():
            currency = request.args.get('currency', 'EUR').upper()
            user_id = get_jwt_identity()
            values = get_portfolio_container_account_values(
                Accounts, Assets, AssetPossession, AssetDisposal, Splits, Commodities, FxRates, user_id, currency)
            return json_response({'currency': currency, 'values': values}, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/overview", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, WEALTH_PERM)
        def get_wealth_overview():
            currency = request.args.get('currency', 'EUR').upper()
            user_id = get_jwt_identity()

            # Cet endpoint reste la source de la vue "Patrimoine totale" (bancaire + portefeuille,
            # dette déduite) consommée par Rapports prédéfinis > Patrimoine (Reports.vue) — c'est le
            # SEUL endroit de l'appli qui affiche ce total combiné, voir kpis.net_worth_total plus
            # bas. La page Patrimoine de Gestion financière (WealthOverview.vue) n'utilise elle que
            # les champs actifs/passifs (portfolio_value, total_liabilities) de cette même réponse et
            # ignore bank_net_worth/net_worth_total — un solde bancaire n'est pas "le Patrimoine" par
            # définition côté Gestion financière (voir rt_dashboard.py pour la vue bancaire).
            bank_net_worth = compute_bank_net_worth(Accounts, Commodities, AssetPossession, FxRates, user_id, currency)
            total_liabilities = compute_total_liabilities(Accounts, Commodities, FxRates, user_id, currency)
            portfolio = get_portfolio_breakdown(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, user_id, currency)
            # portfolio_value doit compter le cash libre des comptes-conteneurs (dépôts pas encore
            # investis, dividendes non réinvestis...) en plus de la valeur de marché des positions —
            # sinon ce cash disparaît du Patrimoine : bank_net_worth exclut délibérément ces comptes
            # (pour ne pas compter leur coût d'achat figé en plus de la valeur de marché), et une
            # simple somme par actif (ci-dessous, `portfolio`) ne voit que les positions, jamais le
            # cash. get_portfolio_container_account_values calcule déjà correctement (positions +
            # cash libre) par compte-conteneur — on en prend juste la somme ici.
            container_values = get_portfolio_container_account_values(
                Accounts, Assets, AssetPossession, AssetDisposal, Splits, Commodities, FxRates, user_id, currency)
            portfolio_value = round(sum(container_values.values()), 2)

            gains = [a for a in portfolio if a['gain_abs'] is not None]
            unrealized_gain = round(sum(a['gain_abs'] for a in gains), 2)
            invested = sum(a['purchase_value'] for a in gains)
            unrealized_gain_pct = round(unrealized_gain / invested * 100, 2) if invested else None

            # Répartitions par type/devise : portefeuille uniquement (pas de comptes bancaires) — ne
            # sont consommées que par WealthOverview.vue (Gestion financière, actifs/passifs).
            allocation_by_type = _portfolio_allocation(portfolio)
            allocation_by_currency = _currency_allocation(portfolio)
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
                    # net_worth_total/net_worth_total_gross/bank_net_worth : combiné bancaire +
                    # portefeuille, dette déduite pour le premier — réservé à Reports.vue (onglet
                    # Patrimoine), voir le commentaire plus haut. Ne pas les afficher sur la page
                    # Patrimoine de Gestion financière (WealthOverview.vue) : elle recalcule son
                    # propre brut/net à partir de portfolio_value et total_liabilities uniquement.
                    'net_worth_total': round(bank_net_worth + portfolio_value - total_liabilities, 2),
                    'net_worth_total_gross': round(bank_net_worth + portfolio_value, 2),
                    'bank_net_worth': bank_net_worth,
                    'total_liabilities': total_liabilities,
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
