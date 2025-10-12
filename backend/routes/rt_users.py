import hashlib
import os

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PWD_PEPPER)
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response
from backend.utils.hash_password import hash_password


def as_dict(user) -> dict:
    return {'fields': {'id': user.id,
                        'username': user.username,
                        'email': user.email},
            'infos': {'created_at': user.created_at,
                         'updated_at': user.updated_at}}

class UsersRoutes:
    def __init__(self, app, DB, Users):
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
                salt = str(os.urandom(32))
                new_user = Users(username=request.args.get('user_name'), email=request.args.get('email'),
                                 password_hash=hash_password(request.args.get('password_hash'),
                                                             salt,
                                                             VAR_PWD_PEPPER),
                                 salt=salt)
                DB.session.add(new_user)
                DB.session.commit()
            except Exception as error:
                print(error)
                return json_response(str(error), HttpCode.SERVER_ERROR)
            return json_response('User has been added to the database.', HttpCode.CREATED)

        @app.route(ROUTE_PATH, methods=['DELETE'])
        @jwt_required(fresh=True)
        def delete_users():
            try:
                Users.query.filter(Users.username == request.args.get('username')).delete()
                DB.session.commit()
            except Exception as error:
                return json_response(str(error), HttpCode.SERVER_ERROR)
            return json_response('User has been deleted from the database.', HttpCode.OK)
