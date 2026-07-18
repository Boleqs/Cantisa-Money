from datetime import date, timedelta
from sqlalchemy import func

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.recurrence import next_occurrence, parse_weekdays

WEALTH_TYPES = ('Current', 'Assets', 'Equity')
REPORTS_PERM = VAR_PERMISSIONS_LIST['Pilotage']['id']
PLANIFICATION_PERM = VAR_PERMISSIONS_LIST['Planification']['id']


class ReportsRoutes:
    def __init__(self, app, DB, Accounts, Transactions, Splits, Categories, Users,
                 Budgets, Subscriptions, Tags, TagsOnSplits, Commodities, FxRates, UserSettings):
        ROUTE_PATH = f"{ROOT_PATH}/reports"

        # ── Devise affichée + helper de conversion, partagés par tous les rapports ────────
        # Taux du jour appliqué uniformément (pas de conversion historique par transaction) —
        # simplification assumée pour ces vues d'agrégation, cf. wealth.py pour les courbes qui
        # ont elles besoin de taux historiques jour par jour.
        def _target_currency(user_id):
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            return settings.currency if settings else 'EUR'

        _rate_cache = {}

        def _rate_to(code, target_currency):
            if code == target_currency:
                return 1.0
            key = (code, target_currency)
            if key not in _rate_cache:
                _rate_cache[key] = get_fx_rate(code, target_currency, FxRates) or 0.0
            return _rate_cache[key]

        @app.route(f"{ROUTE_PATH}/monthly", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def get_monthly_report():
            user_id = get_jwt_identity()
            today = date.today()
            target_currency = _target_currency(user_id)

            months = []
            for i in range(11, -1, -1):
                m = today.month - i
                y = today.year
                while m <= 0:
                    m += 12
                    y -= 1
                months.append((y, m))

            # Comptes virtuels/cachés exclus : ils ne représentent pas de l'argent réel.
            all_accounts = Accounts.query.filter(
                Accounts.user_id == user_id,
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            ).all()
            # Seuls les comptes de valeur réelle (Current + Assets + Equity)
            wealth_ids = [a.id for a in all_accounts if a.account_type in WEALTH_TYPES]

            result = []
            for y, m in months:
                month_start = date(y, m, 1)
                if m == 12:
                    month_end = date(y + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(y, m + 1, 1) - timedelta(days=1)

                income = 0.0
                expenses = 0.0
                if wealth_ids:
                    # Exclut les virements internes entre comptes de valeur
                    non_transfer_tx = DB.session.query(Splits.tx_id).filter(
                        ~Splits.account_id.in_(wealth_ids)
                    ).distinct()

                    income_rows = DB.session.query(
                        Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
                    ).join(Transactions, Splits.tx_id == Transactions.id
                    ).join(Accounts, Splits.account_id == Accounts.id
                    ).join(Commodities, Accounts.currency_id == Commodities.id).filter(
                        Transactions.user_id == user_id,
                        Splits.account_id.in_(wealth_ids),
                        Transactions.post_date >= month_start,
                        Transactions.post_date <= month_end,
                        Splits.quantity > 0,
                        Transactions.id.in_(non_transfer_tx)
                    ).group_by(Commodities.short_name).all()
                    income = sum(float(total) * _rate_to(code, target_currency) for code, total in income_rows)

                    expenses_rows = DB.session.query(
                        Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
                    ).join(Transactions, Splits.tx_id == Transactions.id
                    ).join(Accounts, Splits.account_id == Accounts.id
                    ).join(Commodities, Accounts.currency_id == Commodities.id).filter(
                        Transactions.user_id == user_id,
                        Splits.account_id.in_(wealth_ids),
                        Transactions.post_date >= month_start,
                        Transactions.post_date <= month_end,
                        Splits.quantity < 0,
                        Transactions.id.in_(non_transfer_tx)
                    ).group_by(Commodities.short_name).all()
                    expenses = abs(sum(float(total) * _rate_to(code, target_currency) for code, total in expenses_rows))

                net = round(income - expenses, 2)
                result.append({
                    'month': f"{y}-{m:02d}",
                    'label': month_start.strftime('%b %Y'),
                    'income': round(income, 2),
                    'expenses': round(expenses, 2),
                    'net': net,
                    'savings_rate': round((net / income * 100), 1) if income > 0 else None,
                })

            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/by-category", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def get_by_category_report():
            user_id = get_jwt_identity()
            today = date.today()
            month_start = today.replace(day=1)
            target_currency = _target_currency(user_id)

            start_str = request.args.get('start_date')
            end_str = request.args.get('end_date')
            try:
                start = date.fromisoformat(start_str) if start_str else month_start
                end = date.fromisoformat(end_str) if end_str else today
            except ValueError:
                return json_response('Invalid date format (YYYY-MM-DD expected)', HttpCode.BAD_REQUEST)

            # Uniquement les splits sur comptes de valeur → évite les contreparties Income/Expense
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
                Transactions.post_date >= start,
                Transactions.post_date <= end,
                Splits.quantity < 0,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            ).group_by(Categories.name, Commodities.short_name).all()

            cat_totals = {}
            for name, code, total in cat_rows:
                cat_totals[name] = cat_totals.get(name, 0.0) + float(total) * _rate_to(code, target_currency)

            uncategorized_rows = DB.session.query(
                Commodities.short_name, func.coalesce(func.sum(Splits.quantity), 0)
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).join(Accounts, Splits.account_id == Accounts.id
            ).join(Commodities, Accounts.currency_id == Commodities.id
            ).filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= start,
                Transactions.post_date <= end,
                Transactions.category_id == None,
                Splits.quantity < 0,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            ).group_by(Commodities.short_name).all()
            uncategorized = sum(float(total) * _rate_to(code, target_currency) for code, total in uncategorized_rows)

            result = [
                {'name': name, 'total': round(abs(total), 2)}
                for name, total in cat_totals.items()
            ]
            result.sort(key=lambda r: -r['total'])
            if uncategorized:
                result.append({'name': 'Sans catégorie', 'total': round(abs(uncategorized), 2)})

            return json_response({
                'start_date': str(start),
                'end_date': str(end),
                'by_category': result,
                'total': round(sum(r['total'] for r in result), 2),
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/by-account", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def get_by_account_report():
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

            # Uniquement les comptes de valeur réelle (Current, Assets, Equity)
            net_rows = DB.session.query(
                Accounts.id,
                Accounts.name,
                Accounts.account_type,
                func.coalesce(func.sum(Splits.quantity), 0).label('net'),
            ).join(Splits, Accounts.id == Splits.account_id
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).filter(
                Accounts.user_id == user_id,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
                Transactions.post_date >= start,
                Transactions.post_date <= end,
            ).group_by(Accounts.id, Accounts.name, Accounts.account_type
            ).order_by(Accounts.account_type, Accounts.name
            ).all()

            credits_rows = DB.session.query(
                Splits.account_id,
                func.coalesce(func.sum(Splits.quantity), 0).label('credits'),
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).join(Accounts, Splits.account_id == Accounts.id
            ).filter(
                Transactions.user_id == user_id,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
                Transactions.post_date >= start,
                Transactions.post_date <= end,
                Splits.quantity > 0,
            ).group_by(Splits.account_id).all()

            credits_map = {str(r.account_id): float(r.credits) for r in credits_rows}

            by_account = []
            for r in net_rows:
                net = round(float(r.net), 2)
                credits = round(credits_map.get(str(r.id), 0.0), 2)
                debits = round(abs(credits - net), 2)
                if credits == 0 and debits == 0:
                    continue
                by_account.append({
                    'id': str(r.id),
                    'name': r.name,
                    'account_type': r.account_type,
                    'credits': credits,
                    'debits': debits,
                    'net': net,
                })

            return json_response({
                'start_date': str(start),
                'end_date': str(end),
                'by_account': by_account,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/by-tag", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def get_by_tag_report():
            user_id = get_jwt_identity()
            today = date.today()
            month_start = today.replace(day=1)
            target_currency = _target_currency(user_id)

            start_str = request.args.get('start_date')
            end_str = request.args.get('end_date')
            try:
                start = date.fromisoformat(start_str) if start_str else month_start
                end = date.fromisoformat(end_str) if end_str else today
            except ValueError:
                return json_response('Invalid date format (YYYY-MM-DD expected)', HttpCode.BAD_REQUEST)

            # Un split peut porter plusieurs tags : les totaux par tag peuvent donc se chevaucher
            # (une même dépense comptée sous plusieurs tags) — contrairement à "Par catégorie" où
            # chaque transaction n'a qu'une seule catégorie.
            tag_rows = DB.session.query(
                Tags.name,
                Commodities.short_name,
                func.sum(Splits.quantity).label('total')
            ).join(TagsOnSplits, TagsOnSplits.tag_id == Tags.id
            ).join(Splits, Splits.id == TagsOnSplits.split_id
            ).join(Transactions, Splits.tx_id == Transactions.id
            ).join(Accounts, Splits.account_id == Accounts.id
            ).join(Commodities, Accounts.currency_id == Commodities.id
            ).filter(
                Tags.user_id == user_id,
                Transactions.user_id == user_id,
                Transactions.post_date >= start,
                Transactions.post_date <= end,
                Splits.quantity < 0,
                Accounts.account_type.in_(WEALTH_TYPES),
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            ).group_by(Tags.name, Commodities.short_name).all()

            tag_totals = {}
            for name, code, total in tag_rows:
                tag_totals[name] = tag_totals.get(name, 0.0) + float(total) * _rate_to(code, target_currency)

            result = [{'name': name, 'total': round(abs(total), 2)} for name, total in tag_totals.items()]
            result.sort(key=lambda r: -r['total'])

            return json_response({
                'start_date': str(start),
                'end_date': str(end),
                'by_tag': result,
                'total': round(sum(r['total'] for r in result), 2),
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/budgets", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        @restricted_by_permission(Users, PLANIFICATION_PERM)
        def get_budgets_report():
            user_id = get_jwt_identity()
            budgets = Budgets.query.filter(Budgets.user_id == user_id).order_by(Budgets.start_date.desc()).all()
            today = date.today()

            result = []
            total_allocated = 0.0
            total_spent = 0.0
            for b in budgets:
                allocated = float(b.amount_allocated or 0)
                spent = float(b.amount_spent or 0)
                pct = round((spent / allocated) * 100, 1) if allocated else None
                start = b.start_date.date() if hasattr(b.start_date, 'date') else b.start_date
                end = b.end_date.date() if hasattr(b.end_date, 'date') else b.end_date
                if today < start:
                    status = 'upcoming'
                elif today > end:
                    status = 'past'
                else:
                    status = 'active'
                result.append({
                    'id': str(b.id),
                    'name': b.name,
                    'amount_allocated': round(allocated, 2),
                    'amount_spent': round(spent, 2),
                    'amount_spent_incomplete': bool(b.amount_spent_incomplete),
                    'pct': pct,
                    'start_date': start.isoformat(),
                    'end_date': end.isoformat(),
                    'status': status,
                })
                total_allocated += allocated
                total_spent += spent

            return json_response({
                'budgets': result,
                'total_allocated': round(total_allocated, 2),
                'total_spent': round(total_spent, 2),
                'overall_pct': round((total_spent / total_allocated) * 100, 1) if total_allocated else None,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/subscriptions", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        @restricted_by_permission(Users, PLANIFICATION_PERM)
        def get_subscriptions_report():
            user_id = get_jwt_identity()
            target_currency = _target_currency(user_id)
            subs = Subscriptions.query.filter(Subscriptions.user_id == user_id).order_by(Subscriptions.name).all()
            cat_map = {c.id: c.name for c in Categories.query.filter_by(user_id=user_id).all()}
            # Un abonnement n'a pas de devise propre : le montant est implicitement dans celle du
            # compte débité (from_account_id) — nécessaire pour convertir les agrégats.
            accounts_by_id = {a.id: a for a in Accounts.query.filter_by(user_id=user_id).all()}
            today = date.today()

            def sub_currency(s):
                a = accounts_by_id.get(s.from_account_id)
                if not a:
                    return target_currency
                c = Commodities.query.filter_by(id=a.currency_id).first()
                return c.short_name if c else target_currency

            result = []
            by_category = {}
            total_monthly = 0.0
            for s in subs:
                amount = float(s.amount or 0)

                if s.schedule_type == 'yearly':
                    monthly_equiv = round(amount / 12, 2)
                elif s.schedule_type == 'weekly':
                    nb_days = len(parse_weekdays(s.weekdays)) or 1
                    monthly_equiv = round(amount * nb_days * (30.44 / 7), 2)
                else:  # monthly
                    monthly_equiv = round(amount, 2)
                monthly_equiv_converted = monthly_equiv * _rate_to(sub_currency(s), target_currency)
                total_monthly += monthly_equiv_converted

                ref = s.last_executed_at or s.created_at
                ref_date = ref.date() if hasattr(ref, 'date') else ref
                next_due = next_occurrence(s.schedule_type, s.day_of_month, s.month_of_year, s.weekdays, ref_date)
                while next_due <= today:
                    next_due = next_occurrence(s.schedule_type, s.day_of_month, s.month_of_year, s.weekdays, next_due)

                cat_name = cat_map.get(s.category_id, 'Sans catégorie')
                by_category[cat_name] = by_category.get(cat_name, 0) + monthly_equiv_converted

                result.append({
                    'id': str(s.id),
                    'name': s.name,
                    'amount': round(amount, 2),
                    'schedule_type': s.schedule_type,
                    'day_of_month': s.day_of_month,
                    'month_of_year': s.month_of_year,
                    'weekdays': sorted(parse_weekdays(s.weekdays)),
                    'monthly_equivalent': monthly_equiv,
                    'category': cat_name,
                    'next_due_date': next_due.isoformat(),
                })

            result.sort(key=lambda r: r['next_due_date'])

            return json_response({
                'subscriptions': result,
                'total_monthly': round(total_monthly, 2),
                'total_annual': round(total_monthly * 12, 2),
                'by_category': [
                    {'name': k, 'monthly_total': round(v, 2)}
                    for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])
                ],
            }, HttpCode.OK)
