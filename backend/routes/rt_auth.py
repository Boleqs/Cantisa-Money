import datetime
import hashlib

from flask import jsonify, request, make_response
import jwt
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_SERVER_ROOT_PATH as SERVER_ROOT_PATH,
                            VAR_API_USER_ROOT_PATH as USER_ROOT_PATH,
                            )
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response
from backend.utils.auth_token_checker import auth_required

# TODO : not functionnal for now
def user_restricted(app, DB, Users, uri):
    def decorator(function):
        def wrapper(*args, **kwargs):
            auth = request.authorization
            if not auth.token:
                return json_response({'error': 'User is not authenticated.'}, JsonResponseType.FAILURE), 403
            try:
                token = jwt.decode(auth.token, app.config['secret_key'], algorithms="HS256")
                user_id_from_db = DB.session.query(Users).filter(Users.username == token['username']).first().id
                if user_id_from_db in str(uri):
                    raise Exception
            except Exception as error:
                return json_response({'error': 'user does not request its own data', 'message': str(error)},
                                     JsonResponseType.FAILURE), 403
        return wrapper
    return decorator

class AuthRoutes:
    def __init__(self, app, DB, Users):
        ROUTE_PATH = f"{SERVER_ROOT_PATH}/auth"

        @app.route(f"{ROUTE_PATH}/login", methods=['GET'])
        def login():
            auth = request.authorization
            user_proposed_hash = hashlib.sha256(bytes(auth.password, encoding="utf8")).hexdigest()
            user_hash_from_db = DB.session.query(Users).filter(Users.username == auth.username).first().password_hash
            if auth and (user_proposed_hash == user_hash_from_db):
                token = jwt.encode({'user': auth.username, 'exp': int(datetime.datetime.now().timestamp())
                                                                  + 50}, app.config['SECRET_KEY'])
                return json_response(f"TOKEN : {token}", JsonResponseType.SUCCESS), 200
            return json_response('Login or password incorrect !', JsonResponseType.FAILURE), 401

        @app.route(f"{ROUTE_PATH}/check_token/<uuid:user_id>", methods=['GET'])
        @user_restricted(app, DB, Users,f"{ROUTE_PATH}/check_token/<uuid:user_id>")

        def check_token():
            return 'OK IS OK OK OUAIS'
