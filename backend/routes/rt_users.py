from flask import jsonify, request
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_SERVER_ROOT_PATH as SERVER_ROOT_PATH,
                            VAR_API_USER_ROOT_PATH as USER_ROOT_PATH)
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response


def as_dict(user) -> dict:
    return {'fields' : {'id': user.id,
                        'username': user.username,
                        'email': user.email},
            'infos': {'created_at': user.created_at,
                         'updated_at': user.updated_at}}

class UsersRoutes:
    def __init__(self, app, DB, Users):
        ROUTE_PATH = f"{USER_ROOT_PATH}/user"

        @app.route(f"{ROUTE_PATH}/all", methods=['GET'])
        def get_all_users(user_id):
            return jsonify('test'), HttpCode.OK

        @app.route(ROUTE_PATH, methods=['GET'])
        def get_user_by_id(user_id):
            try:
                user = DB.session.query(Users).filter(Users.id == user_id).first()
                if user: return json_response(as_dict(user), JsonResponseType.SUCCESS), HttpCode.OK
                else: raise RoutesException
            except RoutesException as error:
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR

        @app.route(ROUTE_PATH, methods=['POST'])
        def post_users(user_id):
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

        @app.route(ROUTE_PATH, methods=['PUT'])
        def put_users(user_id):
            return jsonify('test'), HttpCode.CREATED

        @app.route(ROUTE_PATH, methods=['PATCH'])
        def patch_users(user_id):
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

        @app.route(ROUTE_PATH, methods=['DELETE'])
        def delete_users(user_id):

            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

