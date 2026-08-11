import os
import time
import uuid

import jwt
import requests

API_BASE_URL = 'https://api.enablebanking.com'
DEFAULT_REDIRECT_URL = 'http://localhost:5173/bank-sync/callback'

_INSTANCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance')
_PRIVATE_KEY_PATH = os.path.join(_INSTANCE_DIR, 'enable_banking_private_key.pem')
_APP_ID_PATH = os.path.join(_INSTANCE_DIR, 'enable_banking_app_id.txt')
_REDIRECT_URL_PATH = os.path.join(_INSTANCE_DIR, 'enable_banking_redirect_url.txt')


class EnableBankingError(Exception):
    """Erreur renvoyée par l'API Enable Banking ou levée si l'intégration n'est pas configurée."""
    pass


def _read_file(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            value = f.read().strip()
            if value:
                return value
    return None


def get_app_id():
    """Variable d'env prioritaire (déploiements scriptés), sinon valeur enregistrée depuis
    Administration > Intégrations (voir rt_bank_sync.py), sinon vide."""
    return os.environ.get('ENABLE_BANKING_APP_ID') or _read_file(_APP_ID_PATH) or ''


def get_redirect_url():
    return os.environ.get('ENABLE_BANKING_REDIRECT_URL') or _read_file(_REDIRECT_URL_PATH) or DEFAULT_REDIRECT_URL


def save_config(app_id=None, redirect_url=None, private_key=None):
    """Écrit uniquement les champs fournis dans backend/instance/ (persisté par le volume Docker
    instance_data — voir docker-compose.yml). La clé privée est validée (signature RS256 de test)
    avant d'être écrite, pour ne jamais persister un .pem invalide."""
    os.makedirs(_INSTANCE_DIR, exist_ok=True)
    if private_key is not None:
        try:
            jwt.encode({'x': 1}, private_key, algorithm='RS256')
        except Exception as e:
            raise EnableBankingError(f"Clé privée invalide : {e}")
        with open(_PRIVATE_KEY_PATH, 'w', encoding='utf-8') as f:
            f.write(private_key)
    if app_id is not None:
        with open(_APP_ID_PATH, 'w', encoding='utf-8') as f:
            f.write(app_id)
    if redirect_url is not None:
        with open(_REDIRECT_URL_PATH, 'w', encoding='utf-8') as f:
            f.write(redirect_url)


def is_configured():
    return bool(get_app_id()) and os.path.exists(_PRIVATE_KEY_PATH)


def _build_jwt():
    """JWT RS256 signé avec la clé privée de l'application (voir Control Panel Enable Banking),
    requis en en-tête Authorization de chaque appel API. Valable 1h, régénéré à chaque appel plutôt
    que mis en cache : le coût de signature est négligeable face à la simplicité d'éviter la gestion
    d'expiration."""
    app_id = get_app_id()
    if not app_id or not os.path.exists(_PRIVATE_KEY_PATH):
        raise EnableBankingError(
            "Synchro bancaire non configurée : app_id ou la clé privée "
            f"({_PRIVATE_KEY_PATH}) sont manquants."
        )
    with open(_PRIVATE_KEY_PATH, 'r', encoding='utf-8') as f:
        private_key = f.read()

    now = int(time.time())
    payload = {'iss': 'enablebanking.com', 'aud': 'api.enablebanking.com', 'iat': now, 'exp': now + 3600}
    headers = {'typ': 'JWT', 'alg': 'RS256', 'kid': app_id}
    return jwt.encode(payload, private_key, algorithm='RS256', headers=headers)


def _request(method, path, **kwargs):
    headers = kwargs.pop('headers', {})
    headers['Authorization'] = f'Bearer {_build_jwt()}'
    try:
        resp = requests.request(method, f'{API_BASE_URL}{path}', headers=headers, timeout=20, **kwargs)
    except requests.RequestException as e:
        raise EnableBankingError(f"Enable Banking injoignable : {e}")
    if not resp.ok:
        detail = resp.text
        try:
            detail = resp.json().get('message', detail)
        except ValueError:
            pass
        raise EnableBankingError(f"Enable Banking a renvoyé une erreur ({resp.status_code}) : {detail}")
    return resp.json()


def list_aspsps(country):
    """Liste les banques (ASPSPs) disponibles pour un pays (code ISO 3166, ex: 'FR')."""
    return _request('GET', '/aspsps', params={'country': country}).get('aspsps', [])


def start_authorization(aspsp_name, aspsp_country, redirect_url, state, valid_until):
    """Démarre une demande d'autorisation : renvoie l'URL vers laquelle rediriger l'utilisateur pour
    qu'il authentifie ce compte auprès de sa banque. `state` (uuid) est renvoyé tel quel par Enable
    Banking sur l'URL de callback, sert à retrouver la demande d'autorisation en attente."""
    body = {
        'access': {'valid_until': valid_until},
        'aspsp': {'name': aspsp_name, 'country': aspsp_country},
        'state': str(state),
        'redirect_url': redirect_url,
        'psu_type': 'personal',
    }
    return _request('POST', '/auth', json=body)


def create_session(code):
    """Échange le `code` d'autorisation (reçu sur l'URL de callback) contre une session : renvoie
    notamment la liste des comptes autorisés (`accounts`, chacun avec son `uid`) et `session_id`."""
    return _request('POST', '/sessions', json={'code': code})


def get_account_balances(account_uid):
    return _request('GET', f'/accounts/{account_uid}/balances').get('balances', [])


def get_account_transactions(account_uid, date_from=None):
    params = {'date_from': date_from} if date_from else {}
    return _request('GET', f'/accounts/{account_uid}/transactions', params=params).get('transactions', [])
