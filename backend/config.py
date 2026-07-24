# Aggregation of all configs for Flask App
import os
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
                        # Groupe dédié plutôt que rattaché à Planification/Patrimoine : un crédit
                        # poste de vraies transactions (comme Comptabilité), suit une récurrence
                        # (comme Planification) et affecte le patrimoine net (comme Patrimoine),
                        # sans appartenir clairement à aucun des trois.
                        'Crédits':             {'id': uuid.UUID('5a3f8e12-6d4b-49a1-9c7e-2b1f0d8a6e3c'),
                                                'description': 'Gestion des crédits/prêts : échéanciers, révisions de taux, remboursement anticipé'},
                        'Pilotage':            {'id': uuid.UUID('c3816617-599d-40f2-8e10-229b3a528fe5'),
                                                'description': 'Rapports et tableau de bord'},
                        'Réglages personnels': {'id': uuid.UUID('9ed54ea7-03cb-4e75-b6dd-f10c789fcf6a'),
                                                'description': 'Préférences personnelles (devise affichée, format de date, pondération du score de marché)'},
                        # Groupe dédié (pas rattaché à Comptabilité/Pilotage/Réglages) : la fiscalité
                        # est amenée à devenir un domaine à part entière (régimes, foyer fiscal,
                        # plus-values réalisées en Phase 2, dossier annuel en Phase 3).
                        'Fiscalité':           {'id': uuid.UUID('a1c9e4d7-2b6f-4e83-9d5a-7c1f0e8b3d6a'),
                                                'description': 'Régimes fiscaux, foyer fiscal, marquage fiscal des catégories, simulation d\'impôt'},
                        }
# Rôle assigné par défaut à tout nouvel utilisateur (inscription publique ou seed) — voir
# insert_roles() dans app.py et le endpoint public POST /api/auth/signup dans rt_auth.py.
VAR_STANDARD_USER_ROLE_ID = uuid.UUID('00000000-cafe-46fe-9a04-a03b4c253f1f')
VAR_API_ROOT_PATH = '/api'
VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS = 3600
VAR_API_JWT_REFRESH_TOKEN_LIFETIME_IN_SECONDS = 86400
# Valeur par défaut stable (pas générée aléatoirement au démarrage) : un pepper qui change
# invaliderait tous les mots de passe existants à chaque redémarrage. À surcharger en prod
# via la variable d'environnement PWD_PEPPER (voir .env.example à la racine du repo).
VAR_PWD_PEPPER = os.environ.get('PWD_PEPPER') or "My_P3pp4r_1s_V€Ry_c0Mpl&X"


from database.config import db_url
class FlaskConfig:
    ### Global config
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ### Database config
    SQLALCHEMY_DATABASE_URI = db_url
    # Même logique que PWD_PEPPER : valeur stable par défaut (une clé qui change à chaque
    # redémarrage déconnecterait tout le monde). À surcharger en prod via FLASK_SECRET_KEY.
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY') or 'SuperSecureSecretKey'
    JWT_TOKEN_LOCATION = 'cookies'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=VAR_API_JWT_ACCESS_TOKEN_LIFETIME_IN_SECONDS)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=VAR_API_JWT_REFRESH_TOKEN_LIFETIME_IN_SECONDS)
    # Secure=True exige HTTPS (le navigateur refuse sinon d'envoyer/accepter le cookie) — false par
    # défaut car le déploiement Docker fourni tourne en HTTP simple. À passer à true derrière un
    # reverse proxy HTTPS.
    JWT_COOKIE_SECURE = os.environ.get('JWT_COOKIE_SECURE', 'false').lower() == 'true'
    # Protection CSRF (double-submit cookie) activée par défaut — le frontend envoie le header
    # X-CSRF-TOKEN attendu via axios.defaults.xsrfCookieName/xsrfHeaderName (voir router/index.js).
    JWT_COOKIE_CSRF_PROTECT = os.environ.get('JWT_COOKIE_CSRF_PROTECT', 'true').lower() == 'true'