# Aggregation of all configs for Flask App
import uuid
from datetime import datetime, timedelta
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


VAR_PERMISSIONS_LIST = {'Delete users': {'id': uuid.UUID('00000000-cafe-4c9d-8ab3-b35d0bd54397'),
                                         'description': 'Allow to delete any user'},

                        }
#TODO: GET VAR_LOG_FILES PATHS FROM ENV VAR
VAR_LOG_FILES = {'debug': r'C:\Users\Loris\Downloads\debug.txt'}
# USED TO DISPLAY DEV INTENDED DEBUG MESSAGES
VAR_DEBUG_DEV = False
# USED TO DISPLAY USER INTENDED DEBUG MESSAGES | In {'INFO' : 0,'WARN' : 1,'ERROR' : 2,'CRITICAL' : 3}
#TODO : GET VAR_LOG_LEVEL FROM ENV VAR OR CONF FILE?
VAR_LOG_LEVEL = 3
VAR_API_ROOT_PATH = '/api'
VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS = 3600
VAR_API_JWT_REFRESH_TOKEN_LIFETIME_IN_SECONDS = 86400
#TODO IN ENV VAR?
VAR_PWD_PEPPER = "My_P3pp4r_1s_V€Ry_c0Mpl&X"


from database.config import db_url
class FlaskConfig:
    ### Global config
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ### Database config
    SQLALCHEMY_DATABASE_URI = db_url
    #TODO : Get SECRET_KEY from env var
    SECRET_KEY = 'SuperSecureSecretKey'
    JWT_TOKEN_LOCATION = 'cookies'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=VAR_API_JWT_REFRESH_TOKEN_LIFETIME_IN_SECONDS)
    JWT_COOKIE_SECURE = False



