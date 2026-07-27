from datetime import datetime

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

GOALS_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']
GOAL_TYPES = ('one_time', 'recurring')


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, '%Y-%m-%d')


class AddGoalSchema(Schema):
    name = fields.String(required=True)
    goal_type = fields.String(load_default='one_time', validate=validate.OneOf(GOAL_TYPES))
    target_amount = fields.Decimal(required=True)
    target_date = fields.String(required=True)
    end_date = fields.String(load_default=None, allow_none=True)


class UpdateGoalSchema(Schema):
    goal_id = fields.UUID(required=True)
    name = fields.String(required=True)
    goal_type = fields.String(load_default='one_time', validate=validate.OneOf(GOAL_TYPES))
    target_amount = fields.Decimal(required=True)
    target_date = fields.String(required=True)
    end_date = fields.String(load_default=None, allow_none=True)


class GetGoalSchema(Schema):
    goal_id = fields.UUID()


class DeleteGoalSchema(Schema):
    goal_id = fields.UUID(required=True)


def _goal_to_dict(g):
    return {
        'id': str(g.id),
        'user_id': str(g.user_id),
        'name': g.name,
        'goal_type': g.goal_type,
        'target_amount': float(g.target_amount),
        'target_date': g.target_date.isoformat() if g.target_date else None,
        'end_date': g.end_date.isoformat() if g.end_date else None,
        'created_at': g.created_at.isoformat() if g.created_at else None,
    }


class GoalsRoutes:
    def __init__(self, app, DB, FinancialGoals, Users):
        ROUTE_PATH = f"{ROOT_PATH}/goals"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, GOALS_PERM)
        def get_goals():
            try:
                data = GetGoalSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data.get('goal_id'):
                g = FinancialGoals.query.filter(
                    FinancialGoals.id == data['goal_id'],
                    FinancialGoals.user_id == get_jwt_identity()
                ).first()
                if not g:
                    return json_response('Goal not found', HttpCode.NOT_FOUND)
                return json_response(_goal_to_dict(g), HttpCode.OK)

            goals = (FinancialGoals.query
                     .filter(FinancialGoals.user_id == get_jwt_identity())
                     .order_by(FinancialGoals.target_date)
                     .all())
            return json_response([_goal_to_dict(g) for g in goals], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, GOALS_PERM)
        def add_goal():
            try:
                data = AddGoalSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            try:
                goal = FinancialGoals(
                    user_id=get_jwt_identity(),
                    name=data['name'],
                    goal_type=data['goal_type'],
                    target_amount=data['target_amount'],
                    target_date=_parse_date(data['target_date']),
                    end_date=_parse_date(data.get('end_date')),
                )
                DB.session.add(goal)
                DB.session.commit()
                return json_response(_goal_to_dict(goal), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, GOALS_PERM)
        def update_goal():
            try:
                data = UpdateGoalSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            goal = FinancialGoals.query.filter(
                FinancialGoals.id == data['goal_id'],
                FinancialGoals.user_id == get_jwt_identity()
            ).first()
            if not goal:
                return json_response('Goal not found', HttpCode.NOT_FOUND)
            try:
                goal.name = data['name']
                goal.goal_type = data['goal_type']
                goal.target_amount = data['target_amount']
                goal.target_date = _parse_date(data['target_date'])
                goal.end_date = _parse_date(data.get('end_date'))
                DB.session.commit()
                return json_response(_goal_to_dict(goal), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, GOALS_PERM)
        def delete_goal():
            try:
                data = DeleteGoalSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            goal = FinancialGoals.query.filter(
                FinancialGoals.id == data['goal_id'],
                FinancialGoals.user_id == get_jwt_identity()
            ).first()
            if not goal:
                return json_response('Goal not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(goal)
                DB.session.commit()
                return json_response('Goal deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
