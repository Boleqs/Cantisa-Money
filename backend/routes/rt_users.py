from flask import jsonify, Blueprint
from backend.app import DB, Users

rt_users = Blueprint('rt_users', __name__, url_prefix='/api')

@rt_users.route('/users', methods=['GET'])
def get_users():
    return jsonify('test'), 201

@rt_users.route('/users/<uuid:user_id>', methods=['GET'])
def get_user_by_id(user_id):
    user = DB.session.query(Users).filter_by(Users.id == user_id).first()
    return jsonify(user), 200

@rt_users.route('/users', methods=['POST'])
def post_users():
    pass

@rt_users.route('/users', methods=['PUT'])
def put_users():
    pass

@rt_users.route('/users', methods=['PATCH'])
def patch_users():
    pass

@rt_users.route('/users', methods=['DELETE'])
def delete_users():
    pass



