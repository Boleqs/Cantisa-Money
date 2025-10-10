from backend.version import APP_VERSION
from datetime import datetime
from flask import jsonify
from .logs import log


def json_response(response_data: dict|str|list[dict], http_code: int, log_response=True):
    json_format = {
                        'response_data': response_data,
                        'metadata': {'http_code': http_code,
                                     'response_date': datetime.now(),
                                     'server_version': APP_VERSION}
    }
    if log_response: log(message=f"Code : {http_code} ; Message : {response_data}", filename='debug')
    return jsonify(json_format), http_code
