import uuid
from functools import wraps

from flask import request
from flask_jwt_extended import get_jwt_identity

from backend.config import HttpCode
from backend.utils.api_responses import json_response


def restricted_by_permission(users_model, permission_id):
    """
    Use to make sure the user accesses to authorized resources
    :param user_id: UUID of the user demanding the resource
    :param permission_id: UUID of the permission needed
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            asking_user = users_model.query.filter(users_model.id == get_jwt_identity()).first()
            print(request.args.get('user_id'))
            #If no permission and not on himself
            #TODO non fonctionnel : vérification "not on himself"
            if not (asking_user.check_permission(permission_id) and request.args.get('user_id') == str(get_jwt_identity())):
                return json_response({"message": "Resource unauthorized"}, HttpCode.FORBIDDEN)
            return f(*args, **kwargs)
        return wrapper
    return decorator