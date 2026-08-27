#!/bin/sh
set -e

# API_PORT (voir .env.example) : port interne réellement écouté par gunicorn — doit rester
# cohérent avec le mapping défini dans docker-compose.yml.
BIND_PORT="${API_PORT:-5000}"

# Le saut interne reverse proxy (caddy) -> gunicorn est toujours chiffré en Docker : utils/tls.py
# génère un certificat auto-signé au premier démarrage, Caddy ne le vérifie pas (réseau Docker
# interne isolé — voir Caddyfile).
# --workers reste à 1 (start_scheduler() tourne au chargement du module app:app — plusieurs
# workers dupliqueraient les jobs planifiés : abonnements/crédits facturés deux fois, etc.).
# --worker-class gthread --threads 4 en échange : un appel yfinance lent (aucun timeout côté
# market_price.py) ne doit pas bloquer TOUTES les requêtes de TOUS les utilisateurs le temps qu'il
# se termine — un worker sync classique le ferait puisqu'il ne traite qu'une requête à la fois.
TLS_PATHS=$(python -m utils.tls)
CERT_PATH=$(printf '%s\n' "$TLS_PATHS" | sed -n '1p')
KEY_PATH=$(printf '%s\n' "$TLS_PATHS" | sed -n '2p')
exec gunicorn --workers 1 --worker-class gthread --threads 4 --bind "0.0.0.0:$BIND_PORT" --certfile "$CERT_PATH" --keyfile "$KEY_PATH" app:app
