#!/bin/sh
set -e

SECRET_FILE=/instance/db_password.txt

# POSTGRES_PASSWORD (voir .env.example) : Postgres ne l'applique qu'à la toute première
# initialisation du volume de données — une valeur différente à chaque démarrage casserait
# l'authentification aux démarrages suivants, d'où la génération une seule fois puis persistance
# dans /instance (partagé avec le service backend, voir docker-compose.yml et
# backend/database/config.py, qui la relit pour se connecter avec le même mot de passe).
if [ -z "$POSTGRES_PASSWORD" ]; then
    mkdir -p "$(dirname "$SECRET_FILE")"
    if [ ! -s "$SECRET_FILE" ]; then
        head -c 512 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 32 > "$SECRET_FILE"
    fi
    POSTGRES_PASSWORD=$(cat "$SECRET_FILE")
    export POSTGRES_PASSWORD
fi

exec docker-entrypoint.sh "$@"
