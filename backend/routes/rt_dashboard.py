from datetime import date, timedelta
from sqlalchemy import func, cast
from sqlalchemy.dialects.postgresql import DATE as PG_DATE

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

WEALTH_TYPES = ('Current', 'Assets', 'Equity')
DASHBOARD_PERM = VAR_PERMISSIONS_LIST['Pilotage']['id']


def _month_start(y, m):
    """Return date(y, m, 1) handling month overflow."""
    if m > 12:
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    if m < 1:
        y, m = y - (-m) // 12 - 1, 12 - (-m) % 12
    return date(y, m, 1)


class DashboardRoutes:
    def __init__(self, app, DB, Accounts, Transactions, Splits, Categories, Users):
        ROUTE_PATH = f"{ROOT_PATH}/dashboard"

        @app.route(f"{ROUTE_PATH}/stats", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, DASHBOARD_PERM)
        def get_dashboard_stats():
            user_id = get_jwt_identity()
            today = date.today()
            month_start = today.replace(day=1)
            history_start = today - timedelta(days=29)

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

            # ── KPIs ──────────────────────────────────────────────────────────
            current_balance = sum(
                float(a.total_earned or 0) - float(a.total_spent or 0)
                for a in all_accounts if a.account_type == 'Current'
            )
            assets_balance = sum(
                float(a.total_earned or 0) - float(a.total_spent or 0)
                for a in all_accounts if a.account_type == 'Assets'
            )

            monthly_income = 0.0
            monthly_expenses = 0.0
            if wealth_ids:
                # Exclut les virements internes entre comptes de valeur (Current/Assets/Equity)
                non_transfer_tx = DB.session.query(Splits.tx_id).filter(
                    ~Splits.account_id.in_(wealth_ids)
                ).distinct()

                monthly_income = float(DB.session.query(
                    func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date >= month_start,
                    Splits.quantity > 0,
                    Transactions.id.in_(non_transfer_tx)
                ).scalar() or 0)

                monthly_expenses = abs(float(DB.session.query(
                    func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date >= month_start,
                    Splits.quantity < 0,
                    Transactions.id.in_(non_transfer_tx)
                ).scalar() or 0))

            # ── Historique de solde (30 jours) ────────────────────────────────
            # Basé sur les comptes courants uniquement (liquidités du jour)
            opening = 0.0
            if current_ids:
                opening = float(DB.session.query(
                    func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(current_ids),
                    Transactions.post_date < history_start
                ).scalar() or 0)

            daily_rows = []
            if current_ids:
                daily_rows = DB.session.query(
                    func.date(Transactions.post_date).label('day'),
                    func.sum(Splits.quantity).label('flow')
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(current_ids),
                    Transactions.post_date >= history_start
                ).group_by(func.date(Transactions.post_date)).order_by(
                    func.date(Transactions.post_date)
                ).all()

            daily_map = {str(row.day): float(row.flow) for row in daily_rows}
            balance_history = []
            running = opening
            for i in range(30):
                d = history_start + timedelta(days=i)
                flow = daily_map.get(str(d), 0.0)
                running += flow
                balance_history.append({
                    'date': str(d),
                    'balance': round(running, 2),
                    'flow': round(flow, 2),
                })

            # ── Dépenses par catégorie (mois en cours) ────────────────────────
            # Uniquement les splits sur comptes de valeur (Current/Assets/Equity)
            # → évite de compter les contreparties comptables (Income/Expense)
            cat_rows = DB.session.query(
                Categories.name,
                func.sum(Splits.quantity).label('total')
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).join(Categories, Transactions.category_id == Categories.id
            ).join(Accounts, Splits.account_id == Accounts.id
            ).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= month_start,
                Splits.quantity < 0,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            ).group_by(Categories.name).order_by(func.sum(Splits.quantity)).all()

            uncategorized = float(DB.session.query(
                func.coalesce(func.sum(Splits.quantity), 0)
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).join(Accounts, Splits.account_id == Accounts.id
            ).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= month_start,
                Transactions.category_id == None,
                Splits.quantity < 0,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            ).scalar() or 0)

            expenses_by_category = [
                {'name': r.name, 'total': round(abs(float(r.total)), 2)}
                for r in cat_rows
            ]
            if uncategorized:
                expenses_by_category.append({
                    'name': 'Sans catégorie',
                    'total': round(abs(uncategorized), 2)
                })

            # ── Patrimoine net (KPI) ───────────────────────────────────────────
            net_worth = sum(
                float(a.total_earned or 0) - float(a.total_spent or 0)
                for a in all_accounts if a.account_type in WEALTH_TYPES
            )

            # ── Historique du patrimoine net (12 mois) ────────────────────────
            nw_window_start = _month_start(today.year, today.month - 11)

            nw_opening = 0.0
            if wealth_ids:
                nw_opening = float(DB.session.query(
                    func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date < nw_window_start,
                ).scalar() or 0)

            nw_monthly_rows = []
            if wealth_ids:
                nw_monthly_rows = DB.session.query(
                    func.date_trunc('month', cast(Transactions.post_date, PG_DATE)).label('month'),
                    func.sum(Splits.quantity).label('flow')
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(wealth_ids),
                    Transactions.post_date >= nw_window_start,
                ).group_by(
                    func.date_trunc('month', cast(Transactions.post_date, PG_DATE))
                ).order_by(
                    func.date_trunc('month', cast(Transactions.post_date, PG_DATE))
                ).all()

            nw_map = {str(row.month)[:7]: float(row.flow) for row in nw_monthly_rows}

            networth_history = []
            running_nw = nw_opening
            for i in range(12):
                ms = _month_start(today.year, today.month - 11 + i)
                key = str(ms)[:7]
                flow = nw_map.get(key, 0.0)
                running_nw += flow
                networth_history.append({
                    'month': key,
                    'net_worth': round(running_nw, 2),
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
            }, HttpCode.OK)
