# Aggregation of all configs for Flask App
class HttpCode:
    OK = 200
    CREATED = 201
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    SERVER_ERROR = 500


from database.config import db_url
class Config:
    ### Global config
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ### Database config
    SQLALCHEMY_DATABASE_URI = db_url

