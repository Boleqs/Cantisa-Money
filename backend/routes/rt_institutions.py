from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

INSTITUTIONS_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']
VALID_COLORS = ('green', 'red', 'blue', 'white', 'black', 'yellow', 'purple')


class AddInstitutionSchema(Schema):
    name = fields.String(required=True)
    bic = fields.String(load_default=None, allow_none=True)
    website = fields.String(load_default=None, allow_none=True)
    notes = fields.String(load_default=None, allow_none=True)
    color = fields.String(load_default='blue', validate=validate.OneOf(VALID_COLORS))


class UpdateInstitutionSchema(Schema):
    institution_id = fields.UUID(required=True)
    name = fields.String(required=True)
    bic = fields.String(load_default=None, allow_none=True)
    website = fields.String(load_default=None, allow_none=True)
    notes = fields.String(load_default=None, allow_none=True)
    color = fields.String(load_default='blue', validate=validate.OneOf(VALID_COLORS))


class GetInstitutionSchema(Schema):
    institution_id = fields.UUID()


class DeleteInstitutionSchema(Schema):
    institution_id = fields.UUID(required=True)


def _inst_to_dict(i):
    return {
        'id': str(i.id),
        'user_id': str(i.user_id),
        'name': i.name,
        'bic': i.bic,
        'website': i.website,
        'notes': i.notes,
        'color': i.color,
        'sync_provider': i.sync_provider,
        'external_institution_id': i.external_institution_id,
        'connection_id': i.connection_id,
        'sync_status': i.sync_status,
        'sync_enabled': i.sync_enabled,
        'last_synced_at': i.last_synced_at.isoformat() if i.last_synced_at else None,
        'created_at': i.created_at.isoformat() if i.created_at else None,
    }


class InstitutionsRoutes:
    def __init__(self, app, DB, Institutions, Users):
        ROUTE_PATH = f"{ROOT_PATH}/institutions"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, INSTITUTIONS_PERM)
        def get_institutions():
            try:
                data = GetInstitutionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data.get('institution_id'):
                i = Institutions.query.filter(
                    Institutions.id == data['institution_id'],
                    Institutions.user_id == get_jwt_identity()
                ).first()
                if not i:
                    return json_response('Institution not found', HttpCode.NOT_FOUND)
                return json_response(_inst_to_dict(i), HttpCode.OK)

            insts = (Institutions.query
                     .filter(Institutions.user_id == get_jwt_identity())
                     .order_by(Institutions.name)
                     .all())
            return json_response([_inst_to_dict(i) for i in insts], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, INSTITUTIONS_PERM)
        def add_institution():
            try:
                data = AddInstitutionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            if Institutions.query.filter(
                Institutions.user_id == get_jwt_identity(),
                Institutions.name == data['name']
            ).first():
                return json_response('Institution already exists', HttpCode.CONFLICT)
            try:
                i = Institutions(
                    user_id=get_jwt_identity(),
                    name=data['name'],
                    bic=data.get('bic'),
                    website=data.get('website'),
                    notes=data.get('notes'),
                    color=data.get('color', 'blue'),
                )
                DB.session.add(i)
                DB.session.commit()
                return json_response(_inst_to_dict(i), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, INSTITUTIONS_PERM)
        def update_institution():
            try:
                data = UpdateInstitutionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            i = Institutions.query.filter(
                Institutions.id == data['institution_id'],
                Institutions.user_id == get_jwt_identity()
            ).first()
            if not i:
                return json_response('Institution not found', HttpCode.NOT_FOUND)
            try:
                i.name = data['name']
                i.bic = data.get('bic')
                i.website = data.get('website')
                i.notes = data.get('notes')
                i.color = data.get('color', 'blue')
                DB.session.commit()
                return json_response(_inst_to_dict(i), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, INSTITUTIONS_PERM)
        def delete_institution():
            try:
                data = DeleteInstitutionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            i = Institutions.query.filter(
                Institutions.id == data['institution_id'],
                Institutions.user_id == get_jwt_identity()
            ).first()
            if not i:
                return json_response('Institution not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(i)
                DB.session.commit()
                return json_response('Institution deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
