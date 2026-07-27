FROM postgres:16

# Génère un mot de passe aléatoire si POSTGRES_PASSWORD n'est pas fourni, avant de rendre la main
# au véritable entrypoint de l'image officielle — voir entrypoint.sh.
COPY db/entrypoint.sh /usr/local/bin/db-entrypoint-wrapper.sh
RUN chmod +x /usr/local/bin/db-entrypoint-wrapper.sh

ENTRYPOINT ["db-entrypoint-wrapper.sh"]
CMD ["postgres"]
