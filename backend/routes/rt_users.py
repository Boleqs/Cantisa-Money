import hashlib

from flask import jsonify, request
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH)
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response


def as_dict(user) -> dict:
    return {'fields': {'id': user.id,
                        'username': user.username,
                        'email': user.email},
            'infos': {'created_at': user.created_at,
                         'updated_at': user.updated_at}}

class UsersRoutes:
    def __init__(self, app, DB, Users):
        ROUTE_PATH = f"{ROOT_PATH}/user"

        @app.route(f"{ROUTE_PATH}/all", methods=['GET'])
        def get_all_users():
            return jsonify('test'), HttpCode.OK

        @app.route(ROUTE_PATH, methods=['GET'])
        def get_user_by_id():
            try:
                user_id = request.args.get('user_id')
                user = DB.session.query(Users).filter(Users.id == user_id).first()
                if user: return json_response(as_dict(user), JsonResponseType.SUCCESS), HttpCode.OK
                else: raise RoutesException
            except RoutesException as error:
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR

        @app.route(ROUTE_PATH, methods=['POST'])
        def add_users():
            try:
                new_user = Users(username=request.args.get('username'), email=request.args.get('email'),
                                 password_hash=hashlib.sha256(bytes(request.args.get('password_hash'), encoding="utf8")).hexdigest())
                DB.session.add(new_user)
                DB.session.commit()
            except Exception as error:
                print(error)
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR
            return json_response('User has been added to the database.', JsonResponseType.SUCCESS), HttpCode.CREATED


        @app.route(ROUTE_PATH, methods=['PUT'])
        def put_users():
            return jsonify('test'), HttpCode.CREATED

        @app.route(ROUTE_PATH, methods=['PATCH'])
        def patch_users():
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

        @app.route(ROUTE_PATH, methods=['DELETE'])
        def delete_users():
            try:
                Users.query.filter(Users.username == request.args.get('username')).delete()
                DB.session.commit()
            except Exception as error:
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR
            return json_response('User has been deleted from the database.', JsonResponseType.SUCCESS), HttpCode.OK

