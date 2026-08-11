from uuid import UUID

from flask import request
from flask_jwt_extended import jwt_required
from marshmallow import Schema, fields, ValidationError

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PERMISSIONS_LIST)

from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

ADMIN_PERM = VAR_PERMISSIONS_LIST['Administration']['id']


class CreateRoleSchema(Schema):
    name = fields.String(required=True)
    description = fields.String(load_default='')


class EditRoleSchema(Schema):
    name = fields.String(required=True)
    description = fields.String(load_default='')


class CreatePermissionSchema(Schema):
    name = fields.String(required=True)
    description = fields.String(load_default='')


def _role_to_dict(role, all_rp, all_perms):
    perm_ids = {str(rp.permission_id) for rp in all_rp if str(rp.role_id) == str(role.id)}
    perms = [
        {'id': str(p.id), 'name': p.name, 'description': p.description}
        for p in all_perms if str(p.id) in perm_ids
    ]
    return {
        'id': str(role.id),
        'name': role.name,
        'description': role.description,
        'permissions': perms,
        'created_at': role.created_at.isoformat() if role.created_at else None,
    }


class RolesRoutes:
    def __init__(self, app, DB, Users, Roles, Permissions, RolePermissions):
        ROLES_PATH = f"{ROOT_PATH}/roles"
        PERMS_PATH = f"{ROOT_PATH}/permissions"

        # ── Rôles ────────────────────────────────────────────────────────────

        @app.route(ROLES_PATH, methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def list_roles_with_perms():
            roles = Roles.query.order_by(Roles.name).all()
            all_rp = RolePermissions.query.all()
            all_perms = Permissions.query.all()
            return json_response([_role_to_dict(r, all_rp, all_perms) for r in roles], HttpCode.OK)

        @app.route(ROLES_PATH, methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def create_role():
            try:
                data = CreateRoleSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if Roles.query.filter(Roles.name == data['name']).first():
                return json_response('Role name already exists', HttpCode.CONFLICT)
            try:
                role = Roles(name=data['name'], description=data['description'])
                DB.session.add(role)
                DB.session.commit()
                return json_response('Role created', HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROLES_PATH}/<role_id>", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def edit_role(role_id):
            try:
                uid = UUID(role_id)
            except ValueError:
                return json_response('Invalid role_id', HttpCode.BAD_REQUEST)
            try:
                data = EditRoleSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            role = Roles.query.filter(Roles.id == uid).first()
            if not role:
                return json_response('Role not found', HttpCode.NOT_FOUND)

            existing = Roles.query.filter(Roles.name == data['name'], Roles.id != uid).first()
            if existing:
                return json_response('Role name already exists', HttpCode.CONFLICT)
            try:
                role.name = data['name']
                role.description = data['description']
                DB.session.commit()
                return json_response('Role updated', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROLES_PATH}/<role_id>", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def delete_role(role_id):
            try:
                uid = UUID(role_id)
            except ValueError:
                return json_response('Invalid role_id', HttpCode.BAD_REQUEST)

            role = Roles.query.filter(Roles.id == uid).first()
            if not role:
                return json_response('Role not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(role)
                DB.session.commit()
                return json_response('Role deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        # ── Assignation permission → rôle ────────────────────────────────────

        @app.route(f"{ROLES_PATH}/<role_id>/permissions/<perm_id>", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def assign_permission(role_id, perm_id):
            try:
                r_uid = UUID(role_id)
                p_uid = UUID(perm_id)
            except ValueError:
                return json_response('Invalid id', HttpCode.BAD_REQUEST)

            if not Roles.query.filter(Roles.id == r_uid).first():
                return json_response('Role not found', HttpCode.NOT_FOUND)
            if not Permissions.query.filter(Permissions.id == p_uid).first():
                return json_response('Permission not found', HttpCode.NOT_FOUND)
            if RolePermissions.query.filter(RolePermissions.role_id == r_uid,
                                            RolePermissions.permission_id == p_uid).first():
                return json_response('Already assigned', HttpCode.CONFLICT)
            try:
                DB.session.add(RolePermissions(role_id=r_uid, permission_id=p_uid))
                DB.session.commit()
                return json_response('Permission assigned', HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROLES_PATH}/<role_id>/permissions/<perm_id>", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def revoke_permission(role_id, perm_id):
            try:
                r_uid = UUID(role_id)
                p_uid = UUID(perm_id)
            except ValueError:
                return json_response('Invalid id', HttpCode.BAD_REQUEST)

            rp = RolePermissions.query.filter(RolePermissions.role_id == r_uid,
                                              RolePermissions.permission_id == p_uid).first()
            if not rp:
                return json_response('Assignment not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(rp)
                DB.session.commit()
                return json_response('Permission revoked', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        # ── Permissions ──────────────────────────────────────────────────────

        @app.route(PERMS_PATH, methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def list_permissions():
            perms = Permissions.query.order_by(Permissions.name).all()
            return json_response([
                {'id': str(p.id), 'name': p.name, 'description': p.description}
                for p in perms
            ], HttpCode.OK)

        @app.route(PERMS_PATH, methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def create_permission():
            try:
                data = CreatePermissionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if Permissions.query.filter(Permissions.name == data['name']).first():
                return json_response('Permission name already exists', HttpCode.CONFLICT)
            try:
                perm = Permissions(name=data['name'], description=data['description'])
                DB.session.add(perm)
                DB.session.commit()
                return json_response('Permission created', HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{PERMS_PATH}/<perm_id>", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ADMIN_PERM)
        def delete_permission(perm_id):
            try:
                uid = UUID(perm_id)
            except ValueError:
                return json_response('Invalid perm_id', HttpCode.BAD_REQUEST)

            perm = Permissions.query.filter(Permissions.id == uid).first()
            if not perm:
                return json_response('Permission not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(perm)
                DB.session.commit()
                return json_response('Permission deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)