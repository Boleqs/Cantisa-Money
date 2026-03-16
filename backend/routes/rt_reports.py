from datetime import date, timedelta
from sqlalchemy import func

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response


class ReportsRoutes:
    def __init__(self, app, DB, Accounts, Transactions, Splits, Categories):
        ROUTE_PATH = f"{ROOT_PATH}/reports"

        @app.route(f"{ROUTE_PATH}/monthly", methods=['GET'])
        @jwt_required()
        def get_monthly_report():
            user_id = get_jwt_identity()
            today = date.today()

            # Build list of last 12 months (year, month)
            months = []
            for i in range(11, -1, -1):
                m = today.month - i
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                months.append((y, m))

            all_accounts = Accounts.query.filter(Accounts.user_id == user_id).all()
            current_ids = [a.id for a in all_accounts if a.account_type == 'Current']

            result = []
            for y, m in months:
                month_start = date(y, m, 1)
                if m == 12:
                    month_end = date(y + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(y, m + 1, 1) - timedelta(days=1)

                income = 0.0
                expenses = 0.0
                if current_ids:
                    income = float(DB.session.query(
                        func.coalesce(func.sum(Splits.quantity), 0)
                    ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                        Transactions.user_id == user_id,
                        Splits.account_id.in_(current_ids),
                        Transactions.post_date >= month_start,
                        Transactions.post_date <= month_end,
                        Splits.quantity > 0
                    ).scalar() or 0)

                    expenses = abs(float(DB.session.query(
                        func.coalesce(func.sum(Splits.quantity), 0)
                    ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                        Transactions.user_id == user_id,
                        Splits.account_id.in_(current_ids),
                        Transactions.post_date >= month_start,
                        Transactions.post_date <= month_end,
                        Splits.quantity < 0
                    ).scalar() or 0))

                result.append({
                    'month': f"{y}-{m:02d}",
                    'label': month_start.strftime('%b %Y'),
                    'income': round(income, 2),
                    'expenses': round(expenses, 2),
                    'net': round(income - expenses, 2),
                })

            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/by-category", methods=['GET'])
        @jwt_required()
        def get_by_category_report():
            user_id = get_jwt_identity()
            today = date.today()
            month_start = today.replace(day=1)

            start_str = request.args.get('start_date')
            end_str = request.args.get('end_date')
            try:
                start = date.fromisoformat(start_str) if start_str else month_start
                end = date.fromisoformat(end_str) if end_str else today
            except ValueError:
                return json_response('Invalid date format (YYYY-MM-DD expected)', HttpCode.BAD_REQUEST)

            cat_rows = DB.session.query(
                Categories.name,
                func.sum(Splits.quantity).label('total')
            ).join(Transactions, Splits.tx_id == Transactions.id).join(
                Categories, Transactions.category_id == Categories.id
            ).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= start,
                Transactions.post_date <= end,
                Splits.quantity < 0
            ).group_by(Categories.name).order_by(func.sum(Splits.quantity)).all()

            uncategorized = float(DB.session.query(
                func.coalesce(func.sum(Splits.quantity), 0)
            ).join(Transactions, Splits.tx_id == Transactions.id).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= start,
                Transactions.post_date <= end,
                Transactions.category_id == None,
                Splits.quantity < 0
            ).scalar() or 0)

            result = [
                {'name': r.name, 'total': round(abs(float(r.total)), 2)}
                for r in cat_rows
            ]
            if uncategorized:
                result.append({'name': 'Sans catégorie', 'total': round(abs(uncategorized), 2)})

            return json_response({
                'start_date': str(start),
                'end_date': str(end),
                'by_category': result,
                'total': round(sum(r['total'] for r in result), 2),
            }, HttpCode.OK)
