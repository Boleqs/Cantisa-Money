from datetime import date, timedelta
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import DATE as PG_DATE

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import get_fx_rate, get_fx_rate_series
from backend.utils.wealth import get_portfolio_container_account_values
from backend.utils.restricted_by_permission import restricted_by_permission

WEALTH_TYPES = ('Current', 'Assets', 'Equity')
# Un mouvement n'est un vrai revenu/dépense que si la transaction touche effectivement un compte
# Income ou Expense — ne pas déduire cela par exclusion de WEALTH_TYPES : un virement entre un
# compte de valeur et un compte Liability (remboursement de crédit...) n'a aucune jambe Income ou
# Expense mais serait quand même exclu de wealth_ids, donc à tort classé comme "flux réel".
INCOME_EXPENSE_TYPES = ('Income', 'Expense')
DASHBOARD_PERM = VAR_PERMISSIONS_LIST['Pilotage']['id']


def _month_start(y, m):
    """Return date(y, m, 1) handling month overflow."""
    if m > 12:
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    if m < 1:
        y, m = y - (-m) // 12 - 1, 12 - (-m) % 12
    return date(y, m, 1)


class DashboardRoutes:
    def __init__(self, app, DB, Accounts, Transactions, Splits, Categories, Users, Commodities, FxRates, UserSettings,
                 Assets=None, AssetPossession=None, AssetDisposal=None):
        ROUTE_PATH = f"{ROOT_PATH}/dashboard"

        @app.route(f"{ROUTE_PATH}/stats", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, DASHBOARD_PERM)
        def get_dashboard_stats():
            user_id = get_jwt_identity()
            today = date.today()
            month_start = today.replace(day=1)
            history_start = today - timedelta(days=29)

            # ── Devise affichée + helpers de conversion ────────────────────────
            # Toutes les sommes ci-dessous mélangent potentiellement des comptes en devises
            # différentes — converties dans la devise affichée de l'utilisateur avant sommation
            # (taux du jour, appliqué uniformément ; cf. plan pour la justification). Les deux
            # courbes historiques (balance_history, networth_history) utilisent en plus un taux
            # jour par jour (get_fx_rate_series) pour ne pas déformer leur forme.
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            target_currency = settings.currency if settings else 'EUR'
            commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}

            def account_currency(a):
                c = commodities_by_id.get(a.currency_id)
                return c.short_name if c else target_currency

            rate_cache = {}

            def rate_to_target(code):
                if code == target_currency:
                    return 1.0
                if code not in rate_cache:
                    rate_cache[code] = get_fx_rate(code, target_currency, FxRates) or 0.0
                return rate_cache[code]

            # ── Comptes de l'utilisateur ──────────────────────────────────────
            # Comptes virtuels/cachés exclus : ils ne représentent pas de l'argent réel.
            all_accounts = Accounts.query.filter(
                Accounts.user_id == user_id,
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            ).all()
            # current_ids : uniquement pour l'historique de solde (liquidités)
            current_ids = [a.id for a in all_accounts if a.account_type == 'Current']
            # wealth_ids : comptes représentatifs de la valeur réelle (Current + Assets + Equity)
            wealth_ids = [a.id for a in all_accounts if a.account_type in WEALTH_TYPES]
            ie_ids = [a.id for a in all_accounts if a.account_type in INCOME_EXPENSE_TYPES]
            real_flow_tx = DB.session.query(Splits.tx_id).filter(Splits.account_id.in_(ie_ids)).distinct()

            # ── KPIs ──────────────────────────────────────────────────────────
            # Comptes-conteneurs de portefeuille (ex. "Compte Titres") : total_earned - total_spent
            # n'y reflète que le coût d'achat figé au moment de l'opération, pas la valeur de marché
            # actuelle — on utilise à la place la valorisation par position (+ cash libre éventuel)
            # calculée par get_portfolio_container_account_values, cohérente avec Accounts.vue /
            # AccountDetail.vue qui font de même.
            container_values = {}
            if AssetPossession is not None and Assets is not None:
                container_values = get_portfolio_container_account_values(
                    Accounts, Assets, AssetPossession, AssetDisposal, Splits, Commodities, FxRates,
                    user_id, target_currency)

            def account_value(a):
                override = container_values.get(str(a.id))
                if override is not None:
                    return override
                return (float(a.total_earned or 0) - float(a.total_spent or 0)) * rate_to_target(account_currency(a))

            current_balance = sum(
                account_value(a) for a in all_accounts if a.account_type == 'Current'
            )
            assets_balance = sum(
                account_value(a) for a in all_accounts if a.account_type == 'Assets'
            )

            monthly_income = 0.0
            monthly_expenses = 0.0
            if wealth_ids:
                income_rows = DB.session.query(
                    Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id
                ).join(Accounts, Splits.account_id == Accounts.id
                ).join(Commodities, Accounts.currency_id == Commodities.id
                ).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date >= month_start,
                    Splits.quantity > 0,
                    Transactions.id.in_(real_flow_tx)
                ).group_by(Commodities.short_name).all()
                monthly_income = sum(float(total) * rate_to_target(code) for code, total in income_rows)

                expenses_rows = DB.session.query(
                    Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id
                ).join(Accounts, Splits.account_id == Accounts.id
                ).join(Commodities, Accounts.currency_id == Commodities.id
                ).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date >= month_start,
                    Splits.quantity < 0,
                    Transactions.id.in_(real_flow_tx)
                ).group_by(Commodities.short_name).all()
                monthly_expenses = abs(sum(float(total) * rate_to_target(code) for code, total in expenses_rows))

            # ── Historique de solde (30 jours) ────────────────────────────────
            # Basé sur les comptes courants uniquement (liquidités du jour)
            opening_by_code = {}
            if current_ids:
                opening_rows = DB.session.query(
                    Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id
                ).join(Accounts, Splits.account_id == Accounts.id
                ).join(Commodities, Accounts.currency_id == Commodities.id
                ).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(current_ids),
                    Transactions.post_date < history_start
                ).group_by(Commodities.short_name).all()
                opening_by_code = {code: float(total) for code, total in opening_rows}

            daily_rows = []
            if current_ids:
                daily_rows = DB.session.query(
                    func.date(Transactions.post_date).label('day'),
                    Commodities.short_name,
                    func.sum(Splits.quantity).label('flow')
                ).join(Transactions, Splits.tx_id == Transactions.id
                ).join(Accounts, Splits.account_id == Accounts.id
                ).join(Commodities, Accounts.currency_id == Commodities.id
                ).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(current_ids),
                    Transactions.post_date >= history_start
                ).group_by(func.date(Transactions.post_date), Commodities.short_name).all()

            daily_map = {}
            codes_present = set(opening_by_code.keys())
            for row in daily_rows:
                daily_map[(str(row.day), row.short_name)] = float(row.flow)
                codes_present.add(row.short_name)

            fx_series_cache = {code: get_fx_rate_series(code, target_currency, FxRates, history_start, today)
                                for code in codes_present if code != target_currency}
            last_fx = {code: None for code in fx_series_cache}

            running_by_code = dict(opening_by_code)
            balance_history = []
            for i in range(30):
                d = history_start + timedelta(days=i)
                d_str = str(d)
                day_total = 0.0
                day_flow_total = 0.0
                for code in codes_present:
                    flow = daily_map.get((d_str, code), 0.0)
                    running_by_code[code] = running_by_code.get(code, 0.0) + flow
                    if code == target_currency:
                        rate = 1.0
                    else:
                        r = fx_series_cache[code].get(d)
                        if r is not None:
                            last_fx[code] = r
                        rate = last_fx[code]
                    if rate is not None:
                        day_total += running_by_code[code] * rate
                        day_flow_total += flow * rate
                balance_history.append({
                    'date': d_str,
                    'balance': round(day_total, 2),
                    'flow': round(day_flow_total, 2),
                })

            # ── Dépenses par catégorie (mois en cours) ────────────────────────
            # Uniquement les splits sur comptes de valeur (Current/Assets/Equity)
            # → évite de compter les contreparties comptables (Income/Expense)
            cat_rows = DB.session.query(
                Categories.name,
                Commodities.short_name,
                func.sum(Splits.quantity).label('total')
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).join(Categories, Transactions.category_id == Categories.id
            ).join(Accounts, Splits.account_id == Accounts.id
            ).join(Commodities, Accounts.currency_id == Commodities.id
            ).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= month_start,
                Splits.quantity < 0,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
                Transactions.id.in_(real_flow_tx),
            ).group_by(Categories.name, Commodities.short_name).all()

            cat_totals = {}
            for name, code, total in cat_rows:
                cat_totals[name] = cat_totals.get(name, 0.0) + float(total) * rate_to_target(code)

            uncategorized_rows = DB.session.query(
                Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).join(Accounts, Splits.account_id == Accounts.id
            ).join(Commodities, Accounts.currency_id == Commodities.id
            ).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= month_start,
                Transactions.category_id == None,
                Splits.quantity < 0,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
                Transactions.id.in_(real_flow_tx),
            ).group_by(Commodities.short_name).all()
            uncategorized = sum(float(total) * rate_to_target(code) for code, total in uncategorized_rows)

            expenses_by_category = [
                {'name': name, 'total': round(abs(total), 2)}
                for name, total in cat_totals.items()
            ]
            expenses_by_category.sort(key=lambda r: -r['total'])
            if uncategorized:
                expenses_by_category.append({
                    'name': 'Sans catégorie',
                    'total': round(abs(uncategorized), 2)
                })

            # ── Patrimoine net (KPI) ───────────────────────────────────────────
            # Volontairement limité à Current/Assets/Equity (soldes bancaires) : le vrai "Patrimoine"
            # (net worth complet, avec soustraction des crédits) est un concept propre à la page
            # Patrimoine (voir GET /api/wealth/overview) qui inclut aussi le portefeuille — les soldes
            # bancaires seuls n'en font pas partie et n'ont donc pas de distinction brut/net ici.
            net_worth = sum(
                account_value(a) for a in all_accounts if a.account_type in WEALTH_TYPES
            )

            # ── Historique du patrimoine net (12 mois) ────────────────────────
            nw_window_start = _month_start(today.year, today.month - 11)

            nw_opening_by_code = {}
            if wealth_ids:
                nw_opening_rows = DB.session.query(
                    Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id
                ).join(Accounts, Splits.account_id == Accounts.id
                ).join(Commodities, Accounts.currency_id == Commodities.id
                ).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date < nw_window_start,
                ).group_by(Commodities.short_name).all()
                nw_opening_by_code = {code: float(total) for code, total in nw_opening_rows}

            nw_monthly_rows = []
            if wealth_ids:
                nw_monthly_rows = DB.session.query(
                    func.date_trunc('month', cast(Transactions.post_date, PG_DATE)).label('month'),
                    Commodities.short_name,
                    func.sum(Splits.quantity).label('flow')
                ).join(Transactions, Splits.tx_id == Transactions.id
                ).join(Accounts, Splits.account_id == Accounts.id
                ).join(Commodities, Accounts.currency_id == Commodities.id
                ).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date >= nw_window_start,
                ).group_by(
                    func.date_trunc('month', cast(Transactions.post_date, PG_DATE)),
                    Commodities.short_name
                ).all()

            nw_map = {}
            nw_codes_present = set(nw_opening_by_code.keys())
            for row in nw_monthly_rows:
                nw_map[(str(row.month)[:7], row.short_name)] = float(row.flow)
                nw_codes_present.add(row.short_name)

            nw_fx_series_cache = {code: get_fx_rate_series(code, target_currency, FxRates, nw_window_start, today)
                                   for code in nw_codes_present if code != target_currency}
            nw_last_fx = {code: None for code in nw_fx_series_cache}

            nw_running_by_code = dict(nw_opening_by_code)
            networth_history = []
            for i in range(12):
                ms = _month_start(today.year, today.month - 11 + i)
                key = str(ms)[:7]
                month_total = 0.0
                for code in nw_codes_present:
                    flow = nw_map.get((key, code), 0.0)
                    nw_running_by_code[code] = nw_running_by_code.get(code, 0.0) + flow
                    if code == target_currency:
                        rate = 1.0
                    else:
                        r = nw_fx_series_cache[code].get(ms)
                        if r is not None:
                            nw_last_fx[code] = r
                        rate = nw_last_fx[code]
                    if rate is not None:
                        month_total += nw_running_by_code[code] * rate
                networth_history.append({
                    'month': key,
                    'net_worth': round(month_total, 2),
                })

            return json_response({
                'kpis': {
                    'current_balance': round(current_balance, 2),
                    'assets_balance': round(assets_balance, 2),
                    'monthly_income': round(monthly_income, 2),
                    'monthly_expenses': round(monthly_expenses, 2),
                    'net_worth': round(net_worth, 2),
                },
                'balance_history': balance_history,
                'expenses_by_category': expenses_by_category,
                'networth_history': networth_history,
                'container_account_values': container_values,
            }, HttpCode.OK)
