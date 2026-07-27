import os
import secrets

# backend/instance/ : monté en volume Docker (voir docker-compose.yml) pour persister les secrets
# générés entre deux redémarrages du conteneur — même logique que backend/certs/ (utils/tls.py).
_INSTANCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'instance')


def resolve_secret(env_var_name, filename):
    """Retourne une valeur secrète stable, dans cet ordre de priorité :
    1. la variable d'environnement `env_var_name`, si définie (voir .env.example) ;
    2. sinon une valeur aléatoire déjà générée lors d'un démarrage précédent, relue sur disque ;
    3. sinon une nouvelle valeur aléatoire, générée et persistée pour les prochains démarrages.

    Remplace un défaut faible codé en dur, sans réintroduire le problème que ce défaut évitait :
    une valeur qui change à chaque redémarrage invaliderait toutes les sessions actives (clé Flask)
    ou tous les mots de passe existants (pepper) — d'où la persistance sur disque plutôt qu'une
    génération à chaque lancement.
    """
    env_value = os.environ.get(env_var_name)
    if env_value:
        return env_value

    path = os.path.join(_INSTANCE_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            value = f.read().strip()
            if value:
                return value

    value = secrets.token_urlsafe(48)
    os.makedirs(_INSTANCE_DIR, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(value)
    return value
