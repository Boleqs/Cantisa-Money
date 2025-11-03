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



class AccountsRoutes:
    def __init__(self, app, DB, Users, Accounts):
        ROUTE_PATH = f"{ROOT_PATH}/account"

        @app.route(f"{ROUTE_PATH}", methods=["POST"])
        @jwt_required()
        def add_account():
            try:
                if Accounts.query.filter(Users.id == get_jwt_identity(),
                                            Accounts.name == request.args.get("name")).first():
                    return json_response("Commodity already exists", HttpCode.FORBIDDEN)
                commodity = Accounts(user_id=get_jwt_identity(), name=request.args.get("name"),description=request.args.get("description"))
                DB.session.add(commodity)
                DB.session.commit()
                return json_response("Commodity created", HttpCode.CREATED)
            except Exception as error:
                return json_response(str(error), HttpCode.SERVER_ERROR)
