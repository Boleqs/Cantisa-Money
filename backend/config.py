# Aggregation of all configs for Flask App
import uuid
from datetime import datetime, timedelta
from version import APP_VERSION


class HttpCode:
    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    SERVER_ERROR = 500


class JsonResponseType:
    SUCCESS = 'success'
    FAILURE = 'failure'
    VALUES = [SUCCESS, FAILURE]


VAR_PERMISSIONS_LIST = {'Delete users': {'id': uuid.UUID('00000000-cafe-4c9d-8ab3-b35d0bd54397'),
                                         'description': 'Allow to delete any user'},

                        # Permissions regroupées par besoin fonctionnel : chaque groupe réunit les
                        # modules qui n'ont pas de sens isolément (ex. gérer des comptes nécessite
                        # d'accéder aux devises qu'ils référencent). Voir aussi assign_permissions_to_roles()
                        # dans app.py pour la répartition par défaut entre rôles.
                        'Comptabilité':        {'id': uuid.UUID('7f88efda-cce7-41cb-ae28-0f8c45b32f42'),
                                                'description': 'Grand livre : devises, comptes, transactions, catégories, tags, réconciliation, import et catégorisation IA'},
                        'Planification':       {'id': uuid.UUID('bb0b6e50-40d8-4640-8e03-6f0d30cde8bc'),
                                                'description': 'Budgets et abonnements récurrents'},
                        'Patrimoine':          {'id': uuid.UUID('0fe500ae-af15-467a-9220-e054ed103801'),
                                                'description': 'Actifs/portefeuille, valeur nette (wealth) et suivi des marchés'},
                        'Pilotage':            {'id': uuid.UUID('c3816617-599d-40f2-8e10-229b3a528fe5'),
                                                'description': 'Rapports et tableau de bord'},
                        'Réglages personnels': {'id': uuid.UUID('9ed54ea7-03cb-4e75-b6dd-f10c789fcf6a'),
                                                'description': 'Préférences personnelles (devise affichée, format de date, pondération du score de marché)'},
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
    JWT_COOKIE_CSRF_PROTECT = False