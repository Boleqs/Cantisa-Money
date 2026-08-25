# CMM — Cantisa Money Manager

Une application de gestion financière personnelle **complète et auto-hébergée** : comptabilité en
partie double façon GnuCash, budgets, crédits, portefeuille d'investissement, patrimoine et
fiscalité — dans une interface pensée par sections dédiées (à la Microsoft Money) plutôt qu'un
empilement d'onglets. Vos données restent chez vous, sur votre propre serveur.

![Écran d'accueil de CMM](docs/screenshot-home.jpg)

## Pourquoi CMM

- **100 % auto-hébergé, zéro dépendance cloud** — vos comptes, soldes et transactions ne quittent
  jamais votre machine. Pas d'abonnement, pas de service tiers qui ferme et emporte vos données.
- **Comptabilité en partie double, pas un simple pointeur de dépenses** — chaque transaction est
  un ensemble de splits qui s'équilibrent, comme un vrai grand livre comptable (GnuCash). Ça
  élimine toute une classe d'incohérences que les apps "liste de dépenses" ne détectent jamais.
- **Tout au même endroit** — comptes bancaires, budgets, crédits, portefeuille d'investissement,
  immobilier et impôts sont généralement éclatés entre 3 ou 4 apps différentes. Ici, un seul
  patrimoine consolidé, une seule source de vérité.
- **Multi-devises natif** — comptes et actifs dans n'importe quelle devise, conversion automatique
  au taux du jour (ou historique) partout où c'est pertinent.
- **Fiscalité française intégrée** — un moteur de calcul d'impôt sur le revenu configurable
  (foyer fiscal, quotient familial, marquage fiscal des catégories) directement branché sur les
  données déjà suivies dans l'app, sans re-saisie dans un tableur à part.
- **Vos données, exportables à tout moment** — sauvegarde/restauration complète, exports PDF/CSV :
  aucun verrouillage propriétaire.
- **Code source ouvert** — l'app tourne en Docker en une commande, et le schéma de données comme
  la logique de calcul sont entièrement lisibles et modifiables.

## Fonctionnalités

### Vue d'ensemble et suivi au quotidien
Tableau de bord avec évolution du patrimoine net, solde et dépenses par catégorie ; page d'accueil
centralisant échéances à venir (abonnements, crédits) et santé budgétaire.

<p>
  <img src="docs/screenshot-dashboard.jpg" width="100%" alt="Tableau de bord : évolution du patrimoine net, solde et dépenses par catégorie" />
</p>

### Comptabilité en partie double, multi-devises
Comptes de tous types (courant, actif, passif, capitaux propres, revenus, dépenses), transactions
à splits multiples, rapprochement bancaire, synchronisation bancaire (Enable Banking), import CSV
avec catégorisation par règles, OCR de factures avec auto-création de transactions.

### Budgets, abonnements, crédits
Budgets par compte/catégorie/tag avec suivi automatique des dépenses, abonnements récurrents avec
alertes avant prélèvement et historique de prix, crédits avec échéanciers, révisions de taux et
remboursement anticipé.

### Portefeuille d'investissement et patrimoine
Suivi d'actifs (actions, ETF, immobilier, véhicules...) avec cours de marché en temps réel,
opérations sur titres (split, fusion, scission), DCA (plans d'investissement programmé), et une vue
consolidée du patrimoine total.

<p>
  <img src="docs/screenshot-portfolio.jpg" width="100%" alt="Portefeuille : actifs détenus, valeur, prix de revient et plus-value" />
</p>

### Diversification et prédiction du patrimoine
Portail de diversification donnant une note globale (indice de Herfindahl-Hirschman) et la
répartition par classe d'actif, secteur et pays — sur l'ensemble du patrimoine, pas seulement le
portefeuille financier. Projection du patrimoine net à horizon choisi, avec un calculateur d'objectif
qui résout le taux de croissance annuel nécessaire pour atteindre un capital cible à une date donnée.

<p>
  <img src="docs/screenshot-diversification.jpg" width="49%" alt="Portail de diversification : note globale, répartition par classe d'actif, secteur et pays" />
  <img src="docs/screenshot-prediction.jpg" width="49%" alt="Prédiction du patrimoine net à horizon 5 ans" />
</p>
<p>
  <img src="docs/screenshot-prediction-goal.jpg" width="100%" alt="Calculateur d'objectif : taux de croissance annuel nécessaire pour un capital cible" />
</p>

### Fiscalité, rapports et sauvegarde
Moteur d'impôt sur le revenu configurable (foyer fiscal, quotient familial, plus-values), 
constructeur de rapports personnalisés, export PDF/CSV, coffre-fort de documents financiers, et
sauvegarde/restauration complète des données.

<p>
  <img src="docs/screenshot-fiscalite.jpg" width="100%" alt="Simulateur d'impôt : détail du calcul de l'IR" />
</p>

## Installation rapide (Docker)

Prérequis : Docker + Docker Compose.

```bash
docker compose up --build
```

- Frontend : http://localhost:5173
- Backend : http://localhost:5000

(ports par défaut — personnalisables via `FRONTEND_PORT`/`API_PORT`, voir plus bas)

Comptes de démonstration créés au premier démarrage (base vide) : `John` / `Alice`, mot de passe
`CantisaDemo2026!` pour les deux.

Copier `.env.example` en `.env` à la racine pour personnaliser le déploiement (tout est optionnel,
des valeurs par défaut raisonnables s'appliquent sinon) :
- `FLASK_SECRET_KEY` / `PWD_PEPPER` / `POSTGRES_PASSWORD` — laisser vide : des valeurs aléatoires
  sont générées automatiquement et persistées ; à ne définir que pour imposer une valeur précise
- `RESET_DB_ON_START=true` — repart d'une base vide + démo à chaque redémarrage (au lieu de
  conserver les données)
- `DEMO_DATA=false` — base vide sans jeu de données de test ; combiné à `ADMIN_USERNAME` /
  `ADMIN_EMAIL` / `ADMIN_PASSWORD`, crée un unique compte admin réel à la place (sinon aucun moyen
  de se connecter, il n'y a pas d'inscription publique)
- `CORS_ORIGINS` — origine(s) autorisées à appeler l'API, si le frontend n'est pas sur
  `localhost:5173`
- `API_HOST` / `API_PORT` / `FRONTEND_PORT` / `POSTGRES_PORT` — pour un accès depuis un autre
  appareil que la machine hôte, ou en cas de port déjà pris. `API_HOST`/`API_PORT`/`API_HTTPS` sont
  figées dans le frontend au moment du build (`docker compose up --build` nécessaire pour les
  changer, un simple redémarrage ne suffit pas)
- `API_HTTPS=true` — sert l'API **et** le frontend en HTTPS, avec le même certificat auto-signé
  généré automatiquement (si `TLS_CERT_PATH`/`TLS_KEY_PATH` ne sont pas fournis) ; pas de reverse
  proxy dans ce projet, chaque service termine TLS lui-même (gunicorn, nginx/Vite). Suit aussi
  `JWT_COOKIE_SECURE` par défaut (pas besoin de définir les deux séparément) ; penser à adapter
  `CORS_ORIGINS` en `https://` également

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
