import uuid
from datetime import datetime, timedelta
from marshmallow import Schema, fields, ValidationError
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


class AddAccountSchema(Schema):
    name = fields.String(required=True)
    description = fields.String(required=True)
    currency_id = fields.String(required=True)
    parent_id = fields.UUID()
    account_type = fields.String()
    account_subtype = fields.String()
    is_virtual = fields.Boolean()
    is_hidden = fields.Boolean()
    code = fields.String()


class GetAccountSchema(Schema):
    account_id = fields.UUID()


class DeleteAccountSchema(Schema):
    account_id = fields.UUID()


class AccountsRoutes:
    def __init__(self, app, DB, Users, Accounts):
        ROUTE_PATH = f"{ROOT_PATH}/accounts"

        @app.route(f"{ROUTE_PATH}", methods=["POST"])
        @jwt_required()
        def add_account():
            try:
                # Validate request body against schema data types
                data = AddAccountSchema().load(request.json)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            try:
                if Accounts.query.filter(Users.id == get_jwt_identity(),
                                            Accounts.name == data.get("name")).first():
                    return json_response("Account already exists", HttpCode.NOT_FOUND)
                account = Accounts(user_id=get_jwt_identity(), name=data.get("name"),description=data.get("description"))
                DB.session.add(account)
                DB.session.commit()
                return json_response("Account created", HttpCode.CREATED)
            except Exception as error:
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=["GET"])
        @jwt_required()
        def get_account():
            try:
                # Validate request body against schema data types
                data = GetAccountSchema().load(request.args)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            # If user only wants one account
            if data.get('account_id'):
                return json_response(Accounts.query.filter(Users.id == get_jwt_identity(),
                                                           Accounts.id == data.get("account_id")).first(), HttpCode.OK)
            # Else return all accounts of user
            return json_response(Accounts.query.filter(Users.id == get_jwt_identity()).all(), HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=["DELETE"])
        @jwt_required()
        def delete_account():
            try:
                # Validate request body against schema data types
                data = DeleteAccountSchema().load(request.args)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            #TODO : delete account
