# cantisa

Application de gestion financière en deux parties :

- Un backend Flask API en Python

- Un frontend Vite/VueJS

## Installation rapide (Docker)

Prérequis : Docker + Docker Compose.

```bash
docker compose up --build
```

- Frontend : http://localhost:5173
- Backend : http://localhost:5000

Comptes de démonstration créés au premier démarrage (base vide) : `Loris` / `Alice`, mot de passe
`CantisaDemo2026!` pour les deux.

Copier `.env.example` en `.env` à la racine pour personnaliser le déploiement (tout est optionnel,
des valeurs par défaut raisonnables s'appliquent sinon) :
- `ANTHROPIC_API_KEY` — active la catégorisation par IA
- `FLASK_SECRET_KEY` / `PWD_PEPPER` — à définir avec des valeurs uniques pour un vrai déploiement
- `RESET_DB_ON_START=true` — repart d'une base vide + démo à chaque redémarrage (au lieu de
  conserver les données)
- `DEMO_DATA=false` — base vide sans jeu de données de test ; combiné à `ADMIN_USERNAME` /
  `ADMIN_EMAIL` / `ADMIN_PASSWORD`, crée un unique compte admin réel à la place (sinon aucun moyen
  de se connecter, il n'y a pas d'inscription publique)
- `CORS_ORIGINS` — origine(s) autorisées à appeler l'API, si le frontend n'est pas sur
  `localhost:5173`
- `JWT_COOKIE_SECURE=true` — à activer derrière un reverse proxy HTTPS (HTTP simple par défaut)

### Migrations

Le schéma est géré par Alembic (`backend/migrations/`). `docker compose up` applique
automatiquement les migrations en attente à chaque démarrage (idempotent, ne touche à rien si
déjà à jour). Après une modification des modèles SQLAlchemy :
```bash
cd backend
alembic revision --autogenerate -m "description du changement"
```
Puis relire le fichier généré dans `migrations/versions/` avant de le committer — l'autogenerate
ne détecte pas tout correctement (renommages de colonnes, etc.).

## Installation manuelle (sans Docker)

Backend :
```bash
cd backend
pip install -r requirements.txt
python app.py
```
Nécessite un PostgreSQL accessible (variables `DB_*` du même `.env.example` que ci-dessus — le
backend le retrouve tout seul même lancé depuis `backend/`) et le moteur Tesseract OCR installé
sur la machine (utilisé par la fonctionnalité Factures).

Frontend :
```bash
npm install
npm run dev
```
