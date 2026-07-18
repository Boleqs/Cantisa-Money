from datetime import datetime
from marshmallow import Schema, fields, ValidationError
from sqlalchemy import text

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import convert_amount
from backend.utils.restricted_by_permission import restricted_by_permission

BUDGETS_PERM = VAR_PERMISSIONS_LIST['Planification']['id']

# Même prédicat "quels splits comptent" que le trigger Postgres trg_update_budget_spent (voir
# migrations/versions/7f3b1a9d6c2e_budget_spent_currency_conversion.py) — celui-ci ne se déclenche
# que sur les splits, jamais quand le budget lui-même (dates, comptes/catégories/tags liés) est créé
# ou modifié. Appelé explicitement après création/mise à jour pour refléter tout de suite les
# transactions déjà existantes.
#
# Implémenté en Python (pas en SQL comme le trigger) pour pouvoir convertir chaque split dans la
# devise affichée de l'utilisateur (user_settings.currency) via convert_amount, qui va chercher un
# taux live si besoin (contrairement au trigger, qui ne peut lire que le cache fx_rates) — ce qui
# préremplit ce cache et réduit d'autant les cas amount_spent_incomplete détectés ensuite par le
# trigger lors de transactions futures sur la même paire de devises.
def _recompute_budget_spent(DB, budget_id, Budgets, FxRates, Commodities, UserSettings):
    budget = Budgets.query.filter_by(id=budget_id).first()
    settings = UserSettings.query.filter_by(user_id=budget.user_id).first()
    target_currency = settings.currency if settings else 'EUR'
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=budget.user_id).all()}

    rows = DB.session.execute(text("""
        SELECT s.quantity, a.currency_id
        FROM splits s
        JOIN transactions t ON t.id = s.tx_id
        JOIN accounts a ON a.id = s.account_id
        WHERE
            t.post_date BETWEEN :start_date AND :end_date
            AND (
                EXISTS (
                    SELECT 1 FROM budget_accounts ba
                    WHERE ba.budget_id = :budget_id AND ba.account_id = s.account_id
                )
                OR (
                    a.account_type NOT IN ('Expense', 'Income')
                    AND t.category_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM budget_categories bc
                        WHERE bc.budget_id = :budget_id AND bc.category_id = t.category_id
                    )
                )
                OR (
                    a.account_type NOT IN ('Expense', 'Income')
                    AND EXISTS (
                        SELECT 1 FROM tags_on_split tos
                        JOIN budget_tags bt ON bt.tag_id = tos.tag_id
                        WHERE tos.split_id = s.id AND bt.budget_id = :budget_id
                    )
                )
            )
    """), {'budget_id': str(budget_id), 'start_date': budget.start_date, 'end_date': budget.end_date}).fetchall()

    total = 0.0
    incomplete = False
    for quantity, currency_id in rows:
        commodity = commodities_by_id.get(currency_id)
        code = commodity.short_name if commodity else target_currency
        converted = convert_amount(-float(quantity), code, target_currency, FxRates)
        if converted is None:
            incomplete = True
            continue
        total += converted

    budget.amount_spent = round(total, 2)
    budget.amount_spent_incomplete = incomplete


class AddBudgetSchema(Schema):
    name = fields.String(required=True)
    amount_allocated = fields.Decimal(required=True)
    start_date = fields.String(required=True)
    end_date = fields.String(required=True)
    account_ids = fields.List(fields.UUID(), load_default=[])
    category_ids = fields.List(fields.UUID(), load_default=[])
    tag_ids = fields.List(fields.UUID(), load_default=[])


class UpdateBudgetSchema(Schema):
    budget_id = fields.UUID(required=True)
    name = fields.String(required=True)
    amount_allocated = fields.Decimal(required=True)
    start_date = fields.String(required=True)
    end_date = fields.String(required=True)
    account_ids = fields.List(fields.UUID(), load_default=[])
    category_ids = fields.List(fields.UUID(), load_default=[])
    tag_ids = fields.List(fields.UUID(), load_default=[])


class GetBudgetSchema(Schema):
    budget_id = fields.UUID()


class DeleteBudgetSchema(Schema):
    budget_id = fields.UUID(required=True)


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, '%Y-%m-%d')


def _budget_to_dict(budget, BudgetAccounts, BudgetCategories, BudgetTags):
    account_ids = [str(ba.account_id) for ba in
                   BudgetAccounts.query.filter(BudgetAccounts.budget_id == budget.id).all()]
    category_ids = [str(bc.category_id) for bc in
                    BudgetCategories.query.filter(BudgetCategories.budget_id == budget.id).all()]
    tag_ids = [str(bt.tag_id) for bt in
               BudgetTags.query.filter(BudgetTags.budget_id == budget.id).all()]
    return {
        'id': str(budget.id),
        'user_id': str(budget.user_id),
        'name': budget.name,
        'amount_allocated': float(budget.amount_allocated),
        'amount_spent': float(budget.amount_spent),
        'amount_spent_incomplete': bool(budget.amount_spent_incomplete),
        'start_date': budget.start_date.isoformat() if budget.start_date else None,
        'end_date': budget.end_date.isoformat() if budget.end_date else None,
        'created_at': budget.created_at.isoformat() if budget.created_at else None,
        'updated_at': budget.updated_at.isoformat() if budget.updated_at else None,
        'account_ids': account_ids,
        'category_ids': category_ids,
        'tag_ids': tag_ids,
    }


class BudgetsRoutes:
    def __init__(self, app, DB, Budgets, BudgetAccounts, BudgetCategories, BudgetTags, Users,
                 FxRates, Commodities, UserSettings):
        ROUTE_PATH = f"{ROOT_PATH}/budgets"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, BUDGETS_PERM)
        def get_budgets():
            try:
                data = GetBudgetSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            if data.get('budget_id'):
                b = Budgets.query.filter(
                    Budgets.id == data.get('budget_id'),
                    Budgets.user_id == get_jwt_identity()
                ).first()
                if not b:
                    return json_response('Budget not found', HttpCode.NOT_FOUND)
                return json_response(_budget_to_dict(b, BudgetAccounts, BudgetCategories, BudgetTags), HttpCode.OK)

            budgets = (Budgets.query
                       .filter(Budgets.user_id == get_jwt_identity())
                       .order_by(Budgets.start_date.desc())
                       .all())
            return json_response(
                [_budget_to_dict(b, BudgetAccounts, BudgetCategories, BudgetTags) for b in budgets],
                HttpCode.OK
            )

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, BUDGETS_PERM)
        def add_budget():
            try:
                data = AddBudgetSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)
            try:
                budget = Budgets(
                    user_id=get_jwt_identity(),
                    name=data['name'],
                    amount_allocated=data['amount_allocated'],
                    amount_spent=0,
                    start_date=_parse_date(data['start_date']),
                    end_date=_parse_date(data['end_date']),
                )
                DB.session.add(budget)
                DB.session.flush()
                for account_id in data.get('account_ids', []):
                    DB.session.add(BudgetAccounts(budget_id=budget.id, account_id=account_id))
                for category_id in data.get('category_ids', []):
                    DB.session.add(BudgetCategories(budget_id=budget.id, category_id=category_id))
                for tag_id in data.get('tag_ids', []):
                    DB.session.add(BudgetTags(budget_id=budget.id, tag_id=tag_id))
                DB.session.flush()
                _recompute_budget_spent(DB, budget.id, Budgets, FxRates, Commodities, UserSettings)
                DB.session.commit()
                return json_response(
                    _budget_to_dict(budget, BudgetAccounts, BudgetCategories, BudgetTags),
                    HttpCode.CREATED
                )
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, BUDGETS_PERM)
        def update_budget():
            try:
                data = UpdateBudgetSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            budget = Budgets.query.filter(
                Budgets.id == data['budget_id'],
                Budgets.user_id == get_jwt_identity()
            ).first()
            if not budget:
                return json_response('Budget not found', HttpCode.NOT_FOUND)
            try:
                budget.name = data['name']
                budget.amount_allocated = data['amount_allocated']
                budget.start_date = _parse_date(data['start_date'])
                budget.end_date = _parse_date(data['end_date'])
                # Recréer les associations
                BudgetAccounts.query.filter(BudgetAccounts.budget_id == budget.id).delete()
                BudgetCategories.query.filter(BudgetCategories.budget_id == budget.id).delete()
                BudgetTags.query.filter(BudgetTags.budget_id == budget.id).delete()
                for account_id in data.get('account_ids', []):
                    DB.session.add(BudgetAccounts(budget_id=budget.id, account_id=account_id))
                for category_id in data.get('category_ids', []):
                    DB.session.add(BudgetCategories(budget_id=budget.id, category_id=category_id))
                for tag_id in data.get('tag_ids', []):
                    DB.session.add(BudgetTags(budget_id=budget.id, tag_id=tag_id))
                DB.session.flush()
                _recompute_budget_spent(DB, budget.id, Budgets, FxRates, Commodities, UserSettings)
                DB.session.commit()
                return json_response(
                    _budget_to_dict(budget, BudgetAccounts, BudgetCategories, BudgetTags),
                    HttpCode.OK
                )
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, BUDGETS_PERM)
        def delete_budget():
            try:
                data = DeleteBudgetSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            budget = Budgets.query.filter(
                Budgets.id == data['budget_id'],
                Budgets.user_id == get_jwt_identity()
            ).first()
            if not budget:
                return json_response('Budget not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(budget)
                DB.session.commit()
                return json_response('Budget deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)