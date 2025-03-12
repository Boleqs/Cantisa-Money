from flask import request
import jwt
from backend.utils.api_responses import JsonResponseType, json_response
from backend.config import FlaskConfig
import datetime

def auth_required(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth.token:
            return json_response({'error': 'User is not authenticated.'}, JsonResponseType.FAILURE), 403
        try:
            token = jwt.decode(auth.token, FlaskConfig.SECRET_KEY, algorithms="HS256")
        except Exception as error:
            return json_response({'error': 'token is invalid/expired', 'message': str(error)}, JsonResponseType.FAILURE), 403
        return f(*args, **kwargs)
    return decorated

