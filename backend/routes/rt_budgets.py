from datetime import datetime
from marshmallow import Schema, fields, ValidationError

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

BUDGETS_PERM = VAR_PERMISSIONS_LIST['Planification']['id']


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
        'start_date': budget.start_date.isoformat() if budget.start_date else None,
        'end_date': budget.end_date.isoformat() if budget.end_date else None,
        'created_at': budget.created_at.isoformat() if budget.created_at else None,
        'updated_at': budget.updated_at.isoformat() if budget.updated_at else None,
        'account_ids': account_ids,
        'category_ids': category_ids,
        'tag_ids': tag_ids,
    }


class BudgetsRoutes:
    def __init__(self, app, DB, Budgets, BudgetAccounts, BudgetCategories, BudgetTags, Users):
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