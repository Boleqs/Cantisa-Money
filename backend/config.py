# Aggregation of all configs for Flask App
class HttpCode:
    OK = 200
    CREATED = 201
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    SERVER_ERROR = 500


VAR_DEBUG = False
VAR_API_SERVER_ROOT_PATH = '/api'
VAR_API_USER_ROOT_PATH = '/api/<uuid:user_id>'



from database.config import db_url
class FlaskConfig:
    ### Global config
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ### Database config
    SQLALCHEMY_DATABASE_URI = db_url

