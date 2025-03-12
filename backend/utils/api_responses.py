from backend.config import JsonResponseType
from backend.version import APP_VERSION
from datetime import datetime
from flask import jsonify

def json_response(response_data: dict|str|list[dict], response_type: str):
    if response_type not in JsonResponseType.VALUES:
        raise ValueError('Invalid response type')
    json_format = {
                        'response_data': response_data,
                        'metadata': {'response_type': response_type,
                                     'response_date': datetime.now(),
                                     'server_version': APP_VERSION}
    }
    return jsonify(json_format)

