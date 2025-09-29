# Aggregation of all configs for Flask App
from datetime import datetime
from version import APP_VERSION
class HttpCode:
    OK = 200
    CREATED = 201
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    SERVER_ERROR = 500

class JsonResponseType:
    SUCCESS = 'success'
    FAILURE = 'failure'
    VALUES = [SUCCESS, FAILURE]


VAR_DEBUG = False
VAR_API_SERVER_ROOT_PATH = '/api'
VAR_API_USER_ROOT_PATH = '/api/<uuid:user_id>'
VAR_API_JWT_TOKEN_LIFETIME_IN_SECONDS = 3600


from database.config import db_url
class FlaskConfig:
    ### Global config
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ### Database config
    SQLALCHEMY_DATABASE_URI = db_url
    SECRET_KEY = 'SuperSecureSecretKey'
    JWT_TOKEN_LOCATION = 'headers'
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    JWT_IDENTITY_CLAIM = 'sub'


