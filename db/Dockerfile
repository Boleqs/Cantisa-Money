FROM postgres:16

# Même raison que backend/Dockerfile : sans ça, Postgres tourne en UTC (image de base) alors que le
# trigger updated_at (CURRENT_TIMESTAMP, cf. migration initiale) doit rester cohérent avec l'heure de
# Paris utilisée par le backend et affichée au navigateur.
ENV TZ=Europe/Paris

# Génère un mot de passe aléatoire si POSTGRES_PASSWORD n'est pas fourni, avant de rendre la main
# au véritable entrypoint de l'image officielle — voir entrypoint.sh.
COPY db/entrypoint.sh /usr/local/bin/db-entrypoint-wrapper.sh
RUN chmod +x /usr/local/bin/db-entrypoint-wrapper.sh

ENTRYPOINT ["db-entrypoint-wrapper.sh"]
CMD ["postgres"]
