#!/bin/sh
set -e

# API_PORT (voir .env.example) : port interne réellement écouté par gunicorn — doit rester
# cohérent avec le mapping défini dans docker-compose.yml.
BIND_PORT="${API_PORT:-5000}"

# API_HTTPS (voir .env.example) : bascule gunicorn en TLS direct (pas de reverse proxy dans ce
# docker-compose). utils/tls.py gère la génération d'un certificat auto-signé si TLS_CERT_PATH/
# TLS_KEY_PATH ne sont pas fournis.
if [ "$(printf '%s' "$API_HTTPS" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
    TLS_PATHS=$(python -m utils.tls)
    CERT_PATH=$(printf '%s\n' "$TLS_PATHS" | sed -n '1p')
    KEY_PATH=$(printf '%s\n' "$TLS_PATHS" | sed -n '2p')
    exec gunicorn --workers 1 --bind "0.0.0.0:$BIND_PORT" --certfile "$CERT_PATH" --keyfile "$KEY_PATH" app:app
else
    exec gunicorn --workers 1 --bind "0.0.0.0:$BIND_PORT" app:app
fi
