import os

# Chemin partagé avec le service "db" en Docker (voir docker-compose.yml et db/entrypoint.sh) :
# quand POSTGRES_PASSWORD n'est pas fourni, ce dernier génère un mot de passe aléatoire et le
# dépose ici plutôt que d'en fixer un différent de son côté (l'authentification échouerait sinon).
_GENERATED_DB_PASSWORD_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance', 'db_password.txt'
)


def _resolve_db_password():
    env_password = os.environ.get('DB_PASSWORD')
    if env_password:
        return env_password
    if os.path.exists(_GENERATED_DB_PASSWORD_PATH):
        with open(_GENERATED_DB_PASSWORD_PATH, 'r', encoding='utf-8') as f:
            value = f.read().strip()
            if value:
                return value
    return 'postgres'


# Valeurs génériques par défaut (dev local avec un Postgres fraîchement installé) —
# surchargeables via variables d'environnement (voir .env.example à la racine du repo), notamment
# pour pointer vers le service "db" du docker-compose plutôt que "localhost".
user = os.environ.get('DB_USER', 'postgres')
password = _resolve_db_password()
host = os.environ.get('DB_HOST', 'localhost')
port = os.environ.get('DB_PORT', '5432')
db_name = os.environ.get('DB_NAME', 'cmm')

db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
