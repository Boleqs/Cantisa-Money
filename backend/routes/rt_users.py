import os

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PWD_PEPPER,
                            VAR_PERMISSIONS_LIST)

from backend.utils.api_responses import json_response
from backend.utils.hash_password import hash_password
from backend.utils.restricted_by_permission import restricted_by_permission


class CreateUserSchema(Schema):
    username = fields.String(required=True)
    email = fields.Email(required=True)
    password = fields.String(required=True)
    role_id = fields.UUID(required=True)


class ChangeRoleSchema(Schema):
    user_id = fields.UUID(required=True)
    role_id = fields.UUID(required=True)


class ResetPasswordSchema(Schema):
    user_id = fields.UUID(required=True)
    password = fields.String(required=True)


def _user_to_dict(user, user_roles, roles):
    role_ids = {str(ur.role_id) for ur in user_roles if str(ur.user_id) == str(user.id)}
    user_roles_list = [
        {'id': str(r.id), 'name': r.name}
        for r in roles if str(r.id) in role_ids
    ]
    return {
        'id': str(user.id),
        'username': user.username,
        'email': user.email,
        'roles': user_roles_list,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'updated_at': user.updated_at.isoformat() if user.updated_at else None,
    }


class UsersRoutes:
    def __init__(self, app, DB, Users, UserRoles, Roles, Permissions, RolePermissions):
        ROUTE_PATH = f"{ROOT_PATH}/user"

        @app.route(ROUTE_PATH, methods=['GET'])
        @jwt_required()
        def list_users():
            users = Users.query.order_by(Users.username).all()
            all_user_roles = UserRoles.query.all()
            all_roles = Roles.query.all()
            return json_response([_user_to_dict(u, all_user_roles, all_roles) for u in users], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/roles", methods=['GET'])
        @jwt_required()
        def list_roles():
            roles = Roles.query.order_by(Roles.name).all()
            return json_response([{'id': str(r.id), 'name': r.name, 'description': r.description} for r in roles], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/me/permissions", methods=['GET'])
        @jwt_required()
        def get_my_permissions():
            user_id = get_jwt_identity()
            role_ids = [ur.role_id for ur in UserRoles.query.filter(UserRoles.user_id == user_id).all()]
            if not role_ids:
                return json_response([], HttpCode.OK)
            perm_ids = {rp.permission_id for rp in RolePermissions.query.filter(RolePermissions.role_id.in_(role_ids)).all()}
            perms = Permissions.query.filter(Permissions.id.in_(perm_ids)).all()
            return json_response([p.name for p in perms], HttpCode.OK)

        @app.route(ROUTE_PATH, methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, VAR_PERMISSIONS_LIST['Administration']['id'])
        def add_user():
            try:
                data = CreateUserSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if Users.query.filter(Users.username == data['username']).first():
                return json_response('Username already exists', HttpCode.CONFLICT)
            if Users.query.filter(Users.email == data['email']).first():
                return json_response('Email already exists', HttpCode.CONFLICT)

            try:
                salt = os.urandom(16)
                new_user = Users(
                    username=data['username'],
                    email=data['email'],
                    password_hash=hash_password(data['password'], salt, VAR_PWD_PEPPER),
                    salt=salt,
                )
                DB.session.add(new_user)
                DB.session.flush()  # génère l'ID sans commit
                user_role = UserRoles(user_id=new_user.id, role_id=data['role_id'])
                DB.session.add(user_role)
                DB.session.commit()
                return json_response('User created', HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(ROUTE_PATH, methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, VAR_PERMISSIONS_LIST['Administration']['id'])
        def delete_user():
            from uuid import UUID
            user_id_str = request.args.get('user_id')
            if not user_id_str:
                return json_response('Missing user_id', HttpCode.BAD_REQUEST)
            try:
                user_id = UUID(user_id_str)
            except ValueError:
                return json_response('Invalid user_id', HttpCode.BAD_REQUEST)

            user = Users.query.filter(Users.id == user_id).first()
            if not user:
                return json_response('User not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(user)
                DB.session.commit()
                return json_response('User deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/role", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, VAR_PERMISSIONS_LIST['Administration']['id'])
        def change_user_role():
            try:
                data = ChangeRoleSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user = Users.query.filter(Users.id == data['user_id']).first()
            if not user:
                return json_response('User not found', HttpCode.NOT_FOUND)
            try:
                UserRoles.query.filter(UserRoles.user_id == data['user_id']).delete()
                DB.session.add(UserRoles(user_id=data['user_id'], role_id=data['role_id']))
                DB.session.commit()
                return json_response('Role updated', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/reset_password", methods=['POST'])
        @jwt_required()
        def reset_password():
            try:
                data = ResetPasswordSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            caller_id = get_jwt_identity()
            caller = Users.query.filter(Users.id == caller_id).first()
            # Autorisé si admin ou réinitialise son propre MDP
            is_admin = caller.check_permission(VAR_PERMISSIONS_LIST['Administration']['id'])
            is_self = str(data['user_id']) == str(caller_id)
            if not is_admin and not is_self:
                return json_response('Unauthorized', HttpCode.FORBIDDEN)

            user = Users.query.filter(Users.id == data['user_id']).first()
            if not user:
                return json_response('User not found', HttpCode.NOT_FOUND)
            try:
                user.set_password(data['password'])
                DB.session.commit()
                return json_response('Password reset', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
