FROM python:3.11-slim

WORKDIR /app

# Le code (comme le reste de l'app, cf. fr-FR codé en dur côté frontend) suppose que "maintenant"
# correspond à l'heure de Paris : tous les datetime.now() du backend sont naïfs (pas de tzinfo,
# jamais convertis en UTC) et comparés tels quels à l'heure du navigateur (ex: lastUpdatedLabel
# dans Portfolio.vue). Sans ce réglage, l'image de base (Debian) tourne en UTC — un rafraîchissement
# de prix qui vient de se produire s'affichait "il y a 2 heures" en France l'été (CEST = UTC+2).
ENV TZ=Europe/Paris

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/

# Le code mélange imports préfixés ("backend.config") et non préfixés ("config", "database.x") :
# PYTHONPATH=/app couvre les premiers, le WORKDIR ci-dessous (ajouté par Python à sys.path) couvre
# les seconds — reproduit exactement l'exécution locale (cd backend && python app.py).
ENV PYTHONPATH=/app
# Le code source n'est pas modifié à chaud dans le conteneur (pas de bind mount) : le rechargeur
# Werkzeug n'a aucune utilité ici, et peut redémarrer sur un faux changement détecté au démarrage.
ENV FLASK_USE_RELOADER=false
WORKDIR /app/backend

EXPOSE 5000

RUN chmod +x docker-entrypoint.sh

# gunicorn plutôt que le serveur de dev Flask utilisé par "python app.py". Un seul worker : l'init
# DB (create_tables/seed) tourne au niveau du module au chargement — plusieurs workers gunicorn
# l'exécuteraient chacun en parallèle (double seed, conflits de triggers). Passer à plusieurs
# workers nécessiterait d'abord d'extraire cette init dans une étape séparée (ex: avant le CMD).
# La commande gunicorn exacte (avec ou sans --certfile/--keyfile) dépend de API_HTTPS, résolu au
# démarrage du conteneur (variable d'env, pas encore connue à la construction de l'image) — voir
# docker-entrypoint.sh.
ENTRYPOINT ["./docker-entrypoint.sh"]
