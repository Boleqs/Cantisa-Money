import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
# Le CLI `alembic` est un process séparé de app.py (qui fait ce même load_dotenv() en tête de
# fichier) : sans cet appel, database.config retombe silencieusement sur le mot de passe généré
# obsolète (backend/instance/db_password.txt) et la base par défaut "cmm" au lieu de lire
# backend/.env, et échoue en authentification sans que le vrai message d'erreur soit clair
# (masqué en plus par le bug d'encodage connu de psycopg2 sur les messages Postgres en français).
load_dotenv()

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Le backend mélange imports préfixés ("backend.utils.x") et non préfixés ("database.x") : il
# faut donc à la fois backend/ (pour les seconds) et son parent, la racine du repo (pour les
# premiers) sur sys.path — même logique que PYTHONPATH=/app + WORKDIR=/app/backend dans Docker.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)
sys.path.insert(0, os.path.dirname(_BACKEND_DIR))

from database.config import db_url
from database.models.import_models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
config.set_main_option('sqlalchemy.url', db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
