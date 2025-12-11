import uuid
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



class AuthRoutes:
    def __init__(self, app, DB, Users):
        ROUTE_PATH = f"{ROOT_PATH}/auth"

        @app.route(f"{ROUTE_PATH}/check-auth", methods=["GET"])
        @jwt_required(optional=True)
        def check_auth():
            try:
                token = get_jwt()
                print(get_jwt())
                if not token:
                    return json_response("Not logged in", HttpCode.NOT_FOUND)

                if datetime.timestamp(datetime.now()) > get_jwt()["exp"]:
                    return json_response("Loggin expired", HttpCode.FORBIDDEN)
                else:
                    return json_response("Logged in", HttpCode.OK)
            except Exception as e:
                print(e)
                return json_response("Not logged in", HttpCode.FORBIDDEN)

        @app.route(f"{ROUTE_PATH}/refresh", methods=["POST"])
        @jwt_required(refresh=True)
        def refresh():
            try:
                exp_timestamp = get_jwt()["exp"]
                target_timestamp = datetime.timestamp(datetime.now() + timedelta(seconds=VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS/2))
                response = jsonify("refresh successful")
                if target_timestamp > exp_timestamp:
                    access_token = create_access_token(identity=get_jwt_identity())
                    set_access_cookies(response, access_token)
                return response
            except (RuntimeError, KeyError):
                return json_response("Refresh error", HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/login", methods=["POST"])
        def login():
            try:
                data = request.get_json()
                user_name = data.get("login")
                user = Users.query.filter(Users.username == user_name).first()
                if user.check_password(data.get("password")):
                    response = jsonify("login successful")
                    set_access_cookies(response, create_access_token(identity=user.id, fresh=True))
                    set_refresh_cookies(response, create_refresh_token(identity=user.id))
                    return response, HttpCode.OK
                #Bad password
                return json_response("login error : Bad login or password", HttpCode.NOT_FOUND)
            except AttributeError:
                #Bad login
                return json_response("login error : Bad login or password", HttpCode.NOT_FOUND)
            except Exception as err:
                return jsonify(err)

        @app.route(f"{ROUTE_PATH}/logout", methods=["POST"])
        @jwt_required()
        def logout():
            response = jsonify("logout successful")
            unset_jwt_cookies(response)
            return response, HttpCode.OK
