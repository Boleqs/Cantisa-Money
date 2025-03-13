import datetime
import hashlib

from flask import jsonify, request, make_response
import jwt
from flask_jwt_extended import jwt_required

from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_SERVER_ROOT_PATH as SERVER_ROOT_PATH,
                            VAR_API_USER_ROOT_PATH as USER_ROOT_PATH,
                            VAR_API_JWT_TOKEN_LIFETIME_IN_SECONDS as JWT_TOKEN_LIFETIME
                            )
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response
from backend.utils.auth_token_checker import auth_required



class AuthRoutes:
    def __init__(self, app, DB, Users):
        ROUTE_PATH = f"{SERVER_ROOT_PATH}/auth"

        @app.route(f"{ROUTE_PATH}/login", methods=['GET'])
        def login():
            auth = request.authorization
            user_proposed_hash = hashlib.sha256(bytes(auth.password, encoding="utf8")).hexdigest()
            user_hash_from_db = DB.session.query(Users).filter(Users.username == auth.username).first().password_hash
            if auth and (user_proposed_hash == user_hash_from_db):
                user_id = DB.session.query(Users).filter(Users.username == auth.username).first().id
                token = jwt.encode({'user': auth.username,
                                    'exp': int(datetime.datetime.now().timestamp()) + JWT_TOKEN_LIFETIME,
                                    'sub': str(user_id)},
                                    app.config['SECRET_KEY'])
                return json_response(f"TOKEN : {token}", JsonResponseType.SUCCESS), 200
            return json_response('Login or password incorrect !', JsonResponseType.FAILURE), 401

        @app.route(f"{ROUTE_PATH}/check_token/<uuid:user_id>", methods=['GET'])
        @auth_required
        def check_token(user_id):
            return 'OK IS OK OK OUAIS'
