import uuid
from datetime import datetime, timedelta
import hashlib

from flask import jsonify, request, make_response
import jwt
from marshmallow import Schema, fields, ValidationError, validate
from flask_jwt_extended import (jwt_required, set_access_cookies, unset_jwt_cookies, get_jwt, create_access_token,
                                get_jwt_identity, create_refresh_token, set_refresh_cookies)

from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_STANDARD_USER_ROLE_ID,
                            VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS as JWT_ACCESS_TOKEN_LIFETIME,
                            VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS
                            )
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response


class SignupSchema(Schema):
    username = fields.String(required=True, validate=validate.Length(min=3, max=50))
    email = fields.Email(required=True, validate=validate.Length(max=100))
    password = fields.String(required=True, validate=validate.Length(min=8))



class AuthRoutes:
    def __init__(self, app, DB, Users, UserRoles, limiter=None):
        ROUTE_PATH = f"{ROOT_PATH}/auth"

        @app.route(f"{ROUTE_PATH}/me", methods=["GET"])
        @jwt_required()
        def me():
            user = Users.query.filter(Users.id == get_jwt_identity()).first()
            if not user:
                return json_response("User not found", HttpCode.NOT_FOUND)
            return json_response({'id': str(user.id), 'username': user.username, 'email': user.email}, HttpCode.OK)

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
        @(limiter.limit("5 per minute") if limiter else (lambda f: f))
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

        @app.route(f"{ROUTE_PATH}/signup", methods=["POST"])
        @(limiter.limit("5 per minute") if limiter else (lambda f: f))
        def signup():
            try:
                data = SignupSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if Users.query.filter(Users.username == data['username']).first():
                return json_response('Username already exists', HttpCode.CONFLICT)
            if Users.query.filter(Users.email == data['email']).first():
                return json_response('Email already exists', HttpCode.CONFLICT)

            try:
                # Le rôle est toujours "Standard user", jamais fourni par le client : cette route
                # est publique (pas de @jwt_required), il ne faut jamais lui faire confiance pour
                # s'auto-attribuer un rôle plus privilégié.
                new_user = Users(username=data['username'], email=data['email'], password_hash=b'', salt=b'')
                new_user.set_password(data['password'])
                DB.session.add(new_user)
                DB.session.flush()
                DB.session.add(UserRoles(user_id=new_user.id, role_id=VAR_STANDARD_USER_ROLE_ID))
                DB.session.commit()
                return json_response('Account created', HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/logout", methods=["POST"])
        @jwt_required()
        def logout():
            response = jsonify("logout successful")
            unset_jwt_cookies(response)
            return response, HttpCode.OK
