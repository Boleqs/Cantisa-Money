#!/bin/sh
# Sourcé (extension .envsh, voir Dockerfile.frontend) dans le shell de l'entrypoint nginx officiel :
# choisit le template de config à activer et expose les chemins du certificat pour l'envsubst natif
# qui suit. Pas de "set -e" (il s'appliquerait aussi aux étapes suivantes de l'entrypoint).
#
# Le saut interne reverse proxy (caddy) -> frontend est toujours chiffré : on réutilise le
# certificat auto-signé généré par le backend (voir backend/utils/tls.py), monté en lecture seule
# dans /certs (voir docker-compose.yml). Caddy ne vérifie pas ce certificat
# (tls_insecure_skip_verify), donc son nom d'hôte importe peu.

TEMPLATES_DIR=/etc/nginx/templates-available
TARGET=/etc/nginx/templates/default.conf.template

# 60s : le backend ne génère le certificat qu'après avoir attendu que Postgres soit "healthy"
# (voir depends_on dans docker-compose.yml), ce qui peut prendre une dizaine de secondes.
i=0
while [ ! -s "/certs/selfsigned.crt" ] || [ ! -s "/certs/selfsigned.key" ]; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
        echo "Certificat TLS introuvable dans /certs après 60s, abandon." >&2
        exit 1
    fi
    sleep 1
done

export NGINX_CERT_FILE="/certs/selfsigned.crt"
export NGINX_CERT_KEY_FILE="/certs/selfsigned.key"
cp "$TEMPLATES_DIR/https.conf.template" "$TARGET"
