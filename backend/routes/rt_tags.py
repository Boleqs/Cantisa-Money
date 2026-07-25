from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

TAGS_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']

VALID_COLORS = ('green', 'red', 'blue', 'white', 'black', 'yellow', 'purple')
# Tenu synchronisé avec TAX_TREATMENTS dans rt_tax.py.
TAX_TREATMENT_VALUES = ('taxable_income', 'deductible', 'real_estate_income', 'real_estate_expense')


class AddTagSchema(Schema):
    name = fields.String(required=True)
    color = fields.String(load_default='green', validate=validate.OneOf(VALID_COLORS))
    tax_treatment = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(TAX_TREATMENT_VALUES))


class UpdateTagSchema(Schema):
    tag_id = fields.UUID(required=True)
    name = fields.String(required=True)
    color = fields.String(load_default='green', validate=validate.OneOf(VALID_COLORS))
    tax_treatment = fields.String(load_default=None, allow_none=True, validate=validate.OneOf(TAX_TREATMENT_VALUES))


class GetTagSchema(Schema):
    tag_id = fields.UUID()


class DeleteTagSchema(Schema):
    tag_id = fields.UUID(required=True)


class AddTagOnSplitSchema(Schema):
    split_id = fields.UUID(required=True)
    tag_id = fields.UUID(required=True)


class DeleteTagOnSplitSchema(Schema):
    split_id = fields.UUID(required=True)
    tag_id = fields.UUID(required=True)


def _tag_to_dict(t):
    return {
        'id': str(t.id),
        'user_id': str(t.user_id),
        'name': t.name,
        'color': t.color,
        'tax_treatment': t.tax_treatment,
        'created_at': t.created_at.isoformat() if t.created_at else None,
    }


class TagsRoutes:
    def __init__(self, app, DB, Tags, TagsOnSplits, Splits, Transactions, Users):
        ROUTE_PATH = f"{ROOT_PATH}/tags"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, TAGS_PERM)
        def get_tags():
            try:
                data = GetTagSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data.get('tag_id'):
                t = Tags.query.filter(
                    Tags.id == data['tag_id'],
                    Tags.user_id == get_jwt_identity()
                ).first()
                if not t:
                    return json_response('Tag not found', HttpCode.NOT_FOUND)
                return json_response(_tag_to_dict(t), HttpCode.OK)

            tags = (Tags.query
                    .filter(Tags.user_id == get_jwt_identity())
                    .order_by(Tags.name)
                    .all())
            return json_response([_tag_to_dict(t) for t in tags], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, TAGS_PERM)
        def add_tag():
            try:
                data = AddTagSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            if Tags.query.filter(
                Tags.user_id == get_jwt_identity(),
                Tags.name == data['name']
            ).first():
                return json_response('Tag already exists', HttpCode.CONFLICT)
            try:
                t = Tags(
                    user_id=get_jwt_identity(),
                    name=data['name'],
                    color=data.get('color', 'green'),
                    tax_treatment=data.get('tax_treatment'),
                )
                DB.session.add(t)
                DB.session.commit()
                return json_response(_tag_to_dict(t), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, TAGS_PERM)
        def update_tag():
            try:
                data = UpdateTagSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            t = Tags.query.filter(
                Tags.id == data['tag_id'],
                Tags.user_id == get_jwt_identity()
            ).first()
            if not t:
                return json_response('Tag not found', HttpCode.NOT_FOUND)
            try:
                t.name = data['name']
                t.color = data.get('color', 'green')
                t.tax_treatment = data.get('tax_treatment')
                DB.session.commit()
                return json_response(_tag_to_dict(t), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, TAGS_PERM)
        def delete_tag():
            try:
                data = DeleteTagSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            t = Tags.query.filter(
                Tags.id == data['tag_id'],
                Tags.user_id == get_jwt_identity()
            ).first()
            if not t:
                return json_response('Tag not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(t)
                DB.session.commit()
                return json_response('Tag deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        # ── Tags on splits ────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/on-split", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, TAGS_PERM)
        def add_tag_on_split():
            try:
                data = AddTagOnSplitSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            # Vérifier que le tag appartient à l'utilisateur
            if not Tags.query.filter(
                Tags.id == data['tag_id'],
                Tags.user_id == get_jwt_identity()
            ).first():
                return json_response('Tag not found', HttpCode.NOT_FOUND)
            # Vérifier que le split appartient à l'utilisateur (via sa transaction)
            split = (Splits.query
                     .join(Transactions, Splits.tx_id == Transactions.id)
                     .filter(
                         Splits.id == data['split_id'],
                         Transactions.user_id == get_jwt_identity()
                     ).first())
            if not split:
                return json_response('Split not found', HttpCode.NOT_FOUND)
            if TagsOnSplits.query.filter(
                TagsOnSplits.split_id == data['split_id'],
                TagsOnSplits.tag_id == data['tag_id']
            ).first():
                return json_response('Tag already on split', HttpCode.CONFLICT)
            try:
                DB.session.add(TagsOnSplits(split_id=data['split_id'], tag_id=data['tag_id']))
                DB.session.commit()
                return json_response('Tag added to split', HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/on-split", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, TAGS_PERM)
        def remove_tag_on_split():
            try:
                data = DeleteTagOnSplitSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            tos = TagsOnSplits.query.filter(
                TagsOnSplits.split_id == data['split_id'],
                TagsOnSplits.tag_id == data['tag_id']
            ).first()
            if not tos:
                return json_response('Tag not on split', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(tos)
                DB.session.commit()
                return json_response('Tag removed from split', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)