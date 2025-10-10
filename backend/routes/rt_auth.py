from datetime import datetime, timedelta
import hashlib

from flask import jsonify, request, make_response
import jwt
from flask_jwt_extended import (jwt_required, set_access_cookies, unset_jwt_cookies, get_jwt, create_access_token,
                                get_jwt_identity, create_refresh_token, set_refresh_cookies)

from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS as JWT_ACCESS_TOKEN_LIFETIME,
                            VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS
                            )
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response
from backend.utils.auth_token_checker import auth_required

from backend.functions.f_users import check_user_password, check_user_exist



class AuthRoutes:
    def __init__(self, app, DB, Users):
        ROUTE_PATH = f"{ROOT_PATH}/auth"

        @app.route(f"{ROUTE_PATH}/refresh", methods=["POST"])
        @jwt_required(refresh=True)
        def refresh(response):
            try:
                exp_timestamp = get_jwt()["exp"]
                target_timestamp = datetime.timestamp(datetime.now() + timedelta(seconds=VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS/2))
                if target_timestamp > exp_timestamp:
                    access_token = create_access_token(identity=get_jwt_identity())
                    set_access_cookies(response, access_token)
                return response
            except (RuntimeError, KeyError):
                return response

        @app.route(f"{ROUTE_PATH}/login", methods=["POST"])
        def login():
            user_name = request.args.get("user_name")
            if check_user_exist(Users, user_name) and check_user_password(Users, user_name, request.args.get("password_hash")):
                response = jsonify("login successful")
                set_access_cookies(response, create_access_token(identity=user_name, fresh=True))
                set_refresh_cookies(response, create_refresh_token(identity=user_name))
                return response, HttpCode.OK
            return json_response("login error : Bad login or password", HttpCode.NOT_FOUND)


        @app.route(f"{ROUTE_PATH}/logout", methods=["POST"])
        @jwt_required()
        def logout():
            response = jsonify("logout successful")
            unset_jwt_cookies(response)
            return response, HttpCode.OK

        @app.route(f"{ROUTE_PATH}/test", methods=["POST"])
        def test():
            print(check_user_password(Users, request.args.get('username'), request.args.get('password_hash')))
            return json_response("ok", HttpCode.OK)