import os

# Valeurs génériques par défaut (dev local avec un Postgres fraîchement installé) —
# surchargeables via variables d'environnement (voir .env.example à la racine du repo), notamment
# pour pointer vers le service "db" du docker-compose plutôt que "localhost".
user = os.environ.get('DB_USER', 'postgres')
password = os.environ.get('DB_PASSWORD', 'postgres')
host = os.environ.get('DB_HOST', 'localhost')
port = os.environ.get('DB_PORT', '5432')
db_name = os.environ.get('DB_NAME', 'cantisa')

db_url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
