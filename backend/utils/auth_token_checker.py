from functools import wraps

from flask import request
import jwt
from backend.utils.api_responses import JsonResponseType, json_response
from backend.config import FlaskConfig
from backend.utils.exceptions import AuthException
from flask_jwt_extended import get_jwt_identity, jwt_required


def auth_required(f):
    """
    Use if you only need to make sure the user is authenticated using a correct username and password.
    :param f:
    :return:
    """
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth.token:
            return json_response({'error': 'User is not authenticated.'}, JsonResponseType.FAILURE), 403
        try:
            token = jwt.decode(auth.token, FlaskConfig.SECRET_KEY, algorithms="HS256")
            print(token)
        except Exception as error:
            return json_response({'error': 'token is invalid/expired', 'message': str(error)}, JsonResponseType.FAILURE), 403
        return f(*args, **kwargs)
    return decorated



def is_user_resource(model, resource_id_field="id"):
    """
    Use to make sure the user accesses to only its own resources
    :param model: SQLAlchemy Model(ex: Commodities, Accounts)
    :param resource_id_field: id field (par défaut: "id")
    """
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            resource_id = kwargs.get(resource_id_field)
            resource = model.query.filter_by(id=resource_id, user_id=user_id).first()
            if not resource:
                return (json_response({"message": "Resource not found or unauthorized"},
                                      JsonResponseType.FAILURE), 404)
            return f(*args, **kwargs)
        return wrapper
    return decorator