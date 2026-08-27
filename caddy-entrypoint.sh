#!/bin/sh
# Calcule la configuration TLS "edge" (client -> Caddy) à partir des variables d'environnement,
# puis lance Caddy. Le trafic interne (Caddy -> backend/frontend) est géré dans le Caddyfile.
#
# Priorité (voir .env.example) :
#   1. EDGE_HTTPS=false          -> Caddy sert en HTTP clair (un reverse proxy amont termine le TLS)
#   2. EDGE_ACME_DOMAIN défini   -> certificat public automatique (Let's Encrypt / ZeroSSL)
#   3. TLS_CERT_PATH/KEY définis -> certificat fourni par l'utilisateur
#   4. sinon                     -> certificat auto-signé du backend (/certs, volume certs_data)
set -e

HTTP_PORT="${HTTP_PORT:-80}"
HTTPS_PORT="${HTTPS_PORT:-443}"
EDGE_HTTPS_LC="$(printf '%s' "${EDGE_HTTPS:-true}" | tr '[:upper:]' '[:lower:]')"

# auto_https : "off" (pas de TLS géré) ou "disable_redirects" (TLS géré, mais Caddy n'ajoute pas
# la redirection 80->443 — évite les surprises sur ports non standards ; en mode ACME, taper
# http://<domaine> ne redirige donc pas, https:// fonctionne).
if [ "$EDGE_HTTPS_LC" = "false" ]; then
	# L'utilisateur met son propre reverse proxy devant : Caddy sert en HTTP clair sur le réseau,
	# c'est le proxy amont qui termine le TLS côté client.
	CADDY_SITE=":${HTTP_PORT}"
	CADDY_TLS_LINE="# HTTP clair — le TLS est terminé par un reverse proxy amont"
	CADDY_AUTO_HTTPS="off"
elif [ -n "${EDGE_ACME_DOMAIN:-}" ]; then
	# Certificat public automatique — UNIQUEMENT si explicitement demandé. Nécessite que le domaine
	# pointe vers ce serveur et que les ports 80 + 443 soient joignables depuis Internet
	# (idéalement HTTP_PORT=80 et HTTPS_PORT=443).
	CADDY_SITE="${EDGE_ACME_DOMAIN}"
	if [ -n "${EDGE_ACME_EMAIL:-}" ]; then
		CADDY_TLS_LINE="tls ${EDGE_ACME_EMAIL}"
	else
		CADDY_TLS_LINE="# certificat public géré automatiquement par Caddy"
	fi
	CADDY_AUTO_HTTPS="disable_redirects"
elif [ -n "${TLS_CERT_PATH:-}" ] && [ -n "${TLS_KEY_PATH:-}" ]; then
	# Certificat fourni par l'utilisateur (monter le dossier qui le contient dans le conteneur,
	# voir le volume commenté du service caddy dans docker-compose.yml).
	CADDY_SITE=":${HTTPS_PORT}"
	CADDY_TLS_LINE="tls ${TLS_CERT_PATH} ${TLS_KEY_PATH}"
	CADDY_AUTO_HTTPS="disable_redirects"
else
	# Défaut : on réutilise le certificat auto-signé généré par le backend (backend/utils/tls.py,
	# volume certs_data monté en lecture seule dans /certs). Même certificat que le saut interne,
	# un seul à accepter dans le navigateur. Pour un certificat propre : EDGE_ACME_DOMAIN ou
	# TLS_CERT_PATH. ("tls internal" de Caddy ne convient pas ici : sur un site sans nom d'hôte
	# (juste ":443") il ne provisionne aucun certificat et le handshake échoue.)
	i=0
	while [ ! -s "/certs/selfsigned.crt" ] || [ ! -s "/certs/selfsigned.key" ]; do
		i=$((i + 1))
		if [ "$i" -gt 60 ]; then
			echo "[caddy-entrypoint] certificat interne introuvable dans /certs après 60s, abandon." >&2
			exit 1
		fi
		sleep 1
	done
	CADDY_SITE=":${HTTPS_PORT}"
	CADDY_TLS_LINE="tls /certs/selfsigned.crt /certs/selfsigned.key"
	CADDY_AUTO_HTTPS="disable_redirects"
fi

export CADDY_SITE CADDY_TLS_LINE CADDY_AUTO_HTTPS

echo "[caddy-entrypoint] site=${CADDY_SITE} tls=[${CADDY_TLS_LINE:-<auto/none>}] auto_https=${CADDY_AUTO_HTTPS}"
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
