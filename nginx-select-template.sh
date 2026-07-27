#!/bin/sh
# Pas de "set -e" : ce fichier est sourcé (extension .envsh, voir Dockerfile.frontend) dans le
# shell de l'entrypoint nginx officiel — "set -e" s'appliquerait alors aussi à ses étapes
# suivantes, avec le risque de le faire avorter sur une commande qui renvoie légitimement non-zéro.

TEMPLATES_DIR=/etc/nginx/templates-available
TARGET=/etc/nginx/templates/default.conf.template

if [ "$(printf '%s' "$API_HTTPS" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
    CERT_FILENAME=$(basename "${TLS_CERT_PATH:-selfsigned.crt}")
    KEY_FILENAME=$(basename "${TLS_KEY_PATH:-selfsigned.key}")

    # Le backend (voir backend/utils/tls.py) génère ce certificat à son démarrage, dans le même
    # volume ./backend/certs monté ici en lecture seule (voir docker-compose.yml) — on attend
    # qu'il soit prêt plutôt que d'imposer un ordre de démarrage strict entre conteneurs.
    i=0
    while [ ! -s "/certs/$CERT_FILENAME" ] || [ ! -s "/certs/$KEY_FILENAME" ]; do
        i=$((i + 1))
        if [ "$i" -gt 30 ]; then
            echo "Certificat TLS introuvable dans /certs après 30s, abandon." >&2
            exit 1
        fi
        sleep 1
    done

    export NGINX_CERT_FILE="/certs/$CERT_FILENAME"
    export NGINX_CERT_KEY_FILE="/certs/$KEY_FILENAME"
    cp "$TEMPLATES_DIR/https.conf.template" "$TARGET"
else
    cp "$TEMPLATES_DIR/http.conf.template" "$TARGET"
fi
