from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

CATEGORIES_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']
# Tenu synchronisé avec TAX_TREATMENTS dans rt_tax.py.
TAX_TREATMENT_VALUES = ('taxable_income', 'deductible', 'real_estate_income', 'real_estate_expense')


class AddCategorySchema(Schema):
    name = fields.String(required=True)
    description = fields.String(load_default=None)
    tax_treatment = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(TAX_TREATMENT_VALUES))


class UpdateCategorySchema(Schema):
    category_id = fields.UUID(required=True)
    name = fields.String(required=True)
    description = fields.String(load_default=None)
    tax_treatment = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(TAX_TREATMENT_VALUES))


class GetCategorySchema(Schema):
    category_id = fields.UUID()


class DeleteCategorySchema(Schema):
    category_id = fields.UUID(required=True)


def _cat_to_dict(c):
    return {
        'id': str(c.id),
        'user_id': str(c.user_id),
        'name': c.name,
        'description': c.description,
        'tax_treatment': c.tax_treatment,
        'created_at': c.created_at.isoformat() if c.created_at else None,
    }


class CategoriesRoutes:
    def __init__(self, app, DB, Categories, Users):
        ROUTE_PATH = f"{ROOT_PATH}/categories"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, CATEGORIES_PERM)
        def get_categories():
            try:
                data = GetCategorySchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data.get('category_id'):
                c = Categories.query.filter(
                    Categories.id == data['category_id'],
                    Categories.user_id == get_jwt_identity()
                ).first()
                if not c:
                    return json_response('Category not found', HttpCode.NOT_FOUND)
                return json_response(_cat_to_dict(c), HttpCode.OK)

            cats = (Categories.query
                    .filter(Categories.user_id == get_jwt_identity())
                    .order_by(Categories.name)
                    .all())
            return json_response([_cat_to_dict(c) for c in cats], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, CATEGORIES_PERM)
        def add_category():
            try:
                data = AddCategorySchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            if Categories.query.filter(
                Categories.user_id == get_jwt_identity(),
                Categories.name == data['name']
            ).first():
                return json_response('Category already exists', HttpCode.CONFLICT)
            try:
                c = Categories(
                    user_id=get_jwt_identity(),
                    name=data['name'],
                    description=data.get('description'),
                    tax_treatment=data.get('tax_treatment'),
                )
                DB.session.add(c)
                DB.session.commit()
                return json_response(_cat_to_dict(c), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, CATEGORIES_PERM)
        def update_category():
            try:
                data = UpdateCategorySchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            c = Categories.query.filter(
                Categories.id == data['category_id'],
                Categories.user_id == get_jwt_identity()
            ).first()
            if not c:
                return json_response('Category not found', HttpCode.NOT_FOUND)
            try:
                c.name = data['name']
                c.description = data.get('description')
                c.tax_treatment = data.get('tax_treatment')
                DB.session.commit()
                return json_response(_cat_to_dict(c), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, CATEGORIES_PERM)
        def delete_category():
            try:
                data = DeleteCategorySchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            c = Categories.query.filter(
                Categories.id == data['category_id'],
                Categories.user_id == get_jwt_identity()
            ).first()
            if not c:
                return json_response('Category not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(c)
                DB.session.commit()
                return json_response('Category deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)