from flask import jsonify
from backend.config import HttpCode


class UsersRoutes:
    def __init__(self, app, DB, Users):
        @app.route('/api/users', methods=['GET'])
        def get_users():
            return jsonify('test'), HttpCode.OK

        @app.route('/api/users/<uuid:user_id>', methods=['GET'])
        def get_user_by_id(user_id):
            user = DB.session.query(Users).filter(Users.id == user_id).first()
            return jsonify(str(user)), HttpCode.OK

        @app.route('/api/users', methods=['POST'])
        def post_users():
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

        @app.route('/api/users', methods=['PUT'])
        def put_users():
            return jsonify('test'), HttpCode.CREATED

        @app.route('/api/users', methods=['PATCH'])
        def patch_users():
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED

        @app.route('/api/users', methods=['DELETE'])
        def delete_users():
            return jsonify('test'), HttpCode.METHOD_NOT_ALLOWED
