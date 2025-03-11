from flask import jsonify
from backend.config import (HttpCode,
                            VAR_API_SERVER_ROOT_PATH as SERVER_ROOT_PATH,
                            VAR_API_USER_ROOT_PATH as USER_ROOT_PATH)
from backend.utils.exceptions import RoutesException


def as_dict(user) -> dict:
    return {'data' : {'id': user.id,
                        'username': user.username,
                        'email': user.email},
            'metadata': {'created_at': user.created_at,
                         'updated_at': user.updated_at}}

class CommunitiesRoutes:
    def __init__(self, app, DB, Commodities):
        ROUTE_PATH = f"{USER_ROOT_PATH}/commodities"

        @app.route(f"{ROUTE_PATH}/all", methods=['GET'])
        def get_all_commodities():
            return jsonify('test'), HttpCode.OK

        @app.route(f"{ROUTE_PATH}/<commodity_id>", methods=['GET'])
        def get_commodity_by_id(user_id, commodity_id):
            try:
                user = DB.session.query(Commodities).filter(Commodities.id == user_id).first()
                if user: return jsonify(as_dict(user)), HttpCode.OK
                else: raise RoutesException.NoUser
            except RoutesException.NoUser as error:
                return jsonify(error), HttpCode.SERVER_ERROR

        @app.route('/api/users', methods=['POST'])
        def post_commodity():
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

        @app.route('/api/users', methods=['PUT'])
        def put_commodity():
            return jsonify('test'), HttpCode.CREATED

        @app.route('/api/users', methods=['PATCH'])
        def patch_commodity():
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

        @app.route('/api/users', methods=['DELETE'])
        def delete_commodity():
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

