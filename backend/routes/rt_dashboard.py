from datetime import date, timedelta
from sqlalchemy import func

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response


class DashboardRoutes:
    def __init__(self, app, DB, Accounts, Transactions, Splits, Categories):
        ROUTE_PATH = f"{ROOT_PATH}/dashboard"

        @app.route(f"{ROUTE_PATH}/stats", methods=['GET'])
        @jwt_required()
        def get_dashboard_stats():
            user_id = get_jwt_identity()
            today = date.today()
            month_start = today.replace(day=1)
            history_start = today - timedelta(days=29)

            # ── Comptes de l'utilisateur ──────────────────────────────────────
            all_accounts = Accounts.query.filter(Accounts.user_id == user_id).all()
            current_ids = [a.id for a in all_accounts if a.account_type == 'Current']
            all_ids = [a.id for a in all_accounts]

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
            if current_ids:
                monthly_income = float(DB.session.query(
                    func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(current_ids),
                    Transactions.post_date >= month_start,
                    Splits.quantity > 0
                ).scalar() or 0)

                monthly_expenses = abs(float(DB.session.query(
                    func.coalesce(func.sum(Splits.quantity), 0)
                ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                    Transactions.user_id == user_id,
                    Splits.account_id.in_(current_ids),
                    Transactions.post_date >= month_start,
                    Splits.quantity < 0
                ).scalar() or 0))

            # ── Historique de solde (30 jours) ────────────────────────────────
            # On utilise uniquement les comptes courants (double-entrée : la somme
            # de tous les comptes est toujours 0, donc il faut filtrer)
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
            cat_rows = DB.session.query(
                Categories.name,
                func.sum(Splits.quantity).label('total')
            ).join(Transactions, Splits.tx_id == Transactions.id).join(
                Categories, Transactions.category_id == Categories.id
            ).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= month_start,
                Splits.quantity < 0
            ).group_by(Categories.name).order_by(func.sum(Splits.quantity)).all()

            uncategorized = float(DB.session.query(
                func.coalesce(func.sum(Splits.quantity), 0)
            ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= month_start,
                Transactions.category_id == None,
                Splits.quantity < 0
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

            return json_response({
                'kpis': {
                    'current_balance': round(current_balance, 2),
                    'assets_balance': round(assets_balance, 2),
                    'monthly_income': round(monthly_income, 2),
                    'monthly_expenses': round(monthly_expenses, 2),
                },
                'balance_history': balance_history,
                'expenses_by_category': expenses_by_category,
            }, HttpCode.OK)