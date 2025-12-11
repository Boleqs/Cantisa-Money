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


class GetAccountSchema(Schema):
    account_id = fields.UUID()
    account_name = fields.String()

class TestRoutes:
    def __init__(self, app, DB, Users, Accounts):
        ROUTE_PATH = f"{ROOT_PATH}/test"

        @app.route(f"{ROUTE_PATH}", methods=["GET"])
        def get_account():
            try:
                # Validate request body against schema data types
                data = GetAccountSchema().load(request.args)
                test = Accounts.query.filter(Accounts.id == data.get("account_id")).first()

                return json_response([test, 'test_code'], HttpCode.OK)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)