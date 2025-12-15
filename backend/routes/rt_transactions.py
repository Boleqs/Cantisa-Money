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


class GetTransactionsSchema(Schema):
    transaction_id = fields.UUID()


class TransactionsRoutes:
    def __init__(self, app, DB, Transactions, Splits):
        ROUTE_PATH = f"{ROOT_PATH}/transactions"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        def get_transactions():
            try:
                # Validate request body against schema data types
                data = GetTransactionsSchema().load(request.args)
            except ValidationError as err:
                # Return a nice message if validation fails
                return json_response(err.messages, HttpCode.NOT_FOUND)
            if data.get('transaction_id'):
                return json_response(Transactions.query.filter(Transactions.id == data.get('transaction_id'),
                                                     Transactions.user_id == get_jwt_identity()).first(), HttpCode.OK)
            return json_response(Transactions.query.filter(Transactions.user_id == get_jwt_identity()).all(), HttpCode.OK)