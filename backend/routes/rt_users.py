import hashlib
import os
import uuid

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PWD_PEPPER,
                            VAR_PERMISSIONS_LIST)

#from backend.database.models.user_roles import UserRoles

from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response
from backend.utils.hash_password import hash_password
from backend.utils.restricted_by_permission import restricted_by_permission


def as_dict(user) -> dict:
    return {'fields': {'id': user.id,
                        'username': user.username,
                        'email': user.email},
            'infos': {'created_at': user.created_at,
                         'updated_at': user.updated_at}}


class UsersRoutes:
    def __init__(self, app, DB, Users, UserRoles):
        ROUTE_PATH = f"{ROOT_PATH}/user"

        @app.route(ROUTE_PATH, methods=['GET'])
        def get_user_by_id():
            try:
                user_id = request.args.get('user_id')
                user = DB.session.query(Users).filter(Users.id == user_id).first()
                if user: return json_response(as_dict(user), JsonResponseType.SUCCESS), HttpCode.OK
                else: raise RoutesException
            except RoutesException as error:
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(ROUTE_PATH, methods=['POST'])
        def add_user():
            try:
                if Users.query.filter(Users.username == request.args.get("user_name")).first():
                    return json_response("Username already exists", HttpCode.FORBIDDEN)
                salt = os.urandom(16)
                new_user = Users(username=request.args.get('user_name'), email=request.args.get('email'),
                                 password_hash=hash_password(request.args.get('password_hash'),
                                                             salt,
                                                             VAR_PWD_PEPPER),
                                 salt=salt)
                DB.session.add(new_user)
                DB.session.commit()
                user_role = UserRoles(user_id=Users.query.filter(Users.username == request.args.get('user_name')).first().id,
                                      role_id=request.args.get('role_id'))
                DB.session.add(user_role)
                DB.session.commit()
            except Exception as error:
                print(error)
                return json_response(str(error), HttpCode.SERVER_ERROR)
            return json_response('User has been added to the database.', HttpCode.CREATED)

        @app.route(ROUTE_PATH, methods=['DELETE'])
        @jwt_required(fresh=True)
        @restricted_by_permission(Users, VAR_PERMISSIONS_LIST['Delete users']['id'])
        def delete_users():
            try:
                print('succeed')
                user_id = request.args.get('user_id')
                asking_user = Users.query.filter(Users.id == get_jwt_identity()).first()
                # If user delete itself or if user has "Delete users" permission
                if user_id == get_jwt_identity() or asking_user.check_permission(uuid.UUID("00000000-cafe-4c9d-8ab3-b35d0bd54397")):
                    Users.query.filter(Users.id == user_id).delete()
                    DB.session.commit()
            except Exception as error:
                return json_response(str(error), HttpCode.SERVER_ERROR)
            return json_response('User has been deleted from the database.', HttpCode.OK)
