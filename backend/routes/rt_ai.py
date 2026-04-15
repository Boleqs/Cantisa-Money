import json
import os

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH)
from backend.utils.api_responses import json_response

_BATCH_SIZE = 30


def _build_prompt(descriptions, categories, accounts):
    cats = '\n'.join(f'- {c["id"]}: {c["name"]}' for c in categories) or '(aucune)'
    accs = '\n'.join(f'- {a["id"]}: {a["name"]} [{a["account_type"]}]' for a in accounts) or '(aucun)'
    descs = '\n'.join(f'{i}: {d}' for i, d in enumerate(descriptions))

    return f"""Tu es un assistant bancaire français. Analyse chaque description de transaction et détermine:
1. La catégorie de dépense/revenu (si applicable)
2. Le compte de contrepartie le plus probable (d'où vient ou où va l'argent)

Catégories disponibles (id: nom):
{cats}

Comptes existants (id: nom [type]):
{accs}

Types de comptes Cantisa: Current (bancaire), Income (revenus), Expense (dépenses), Assets (épargne/investissement), Equity

Descriptions à analyser (index: texte):
{descs}

Réponds UNIQUEMENT avec du JSON valide, sans markdown:
{{"suggestions": [
  {{
    "index": 0,
    "category_id": "uuid ou null",
    "opposing_account_id": "uuid ou null",
    "new_account": {{"name": "...", "cantisa_type": "..."}} // null si un compte existant convient
  }}
]}}

Règles pour la catégorie:
- Courses (Carrefour/Leclerc/Aldi/Lidl) → Alimentation
- Streaming (Netflix/Spotify/Disney) → Loisirs
- Loyer/Charges → Logement
- Transport (SNCF/Essence/Uber/Vélib) → Transport
- Santé (Pharmacie/Médecin/Mutuelle) → Santé
- null si aucune catégorie ne convient (salaires, virements, etc.)

Règles pour le compte de contrepartie:
- Choisis un compte EXISTANT si son nom/type correspond bien
- Sinon propose new_account avec un nom précis et le bon type Cantisa:
  * Salaire/Prime/Revenu → Income, ex: {{"name": "Salaires", "cantisa_type": "Income"}}
  * Achat/Dépense courante → Expense, ex: {{"name": "Dépenses courantes", "cantisa_type": "Expense"}}
  * Épargne/Livret/PEA → Assets, ex: {{"name": "Livret A", "cantisa_type": "Assets"}}
- opposing_account_id=null si new_account est proposé, et inversement"""


class AIRoutes:
    def __init__(self, app, DB, Categories, Accounts):
        ROUTE_PATH = f"{ROOT_PATH}/ai"

        @app.route(f"{ROUTE_PATH}/categorize", methods=['POST'])
        @jwt_required()
        def categorize_transactions():
            if not os.environ.get('ANTHROPIC_API_KEY'):
                return json_response('ANTHROPIC_API_KEY non configurée', HttpCode.SERVER_ERROR)

            user_id = get_jwt_identity()
            descriptions = request.json.get('descriptions', [])

            if not descriptions:
                return json_response({'suggestions': []}, HttpCode.OK)

            user_cats = Categories.query.filter(Categories.user_id == user_id).all()
            categories = [{'id': str(c.id), 'name': c.name} for c in user_cats]

            user_accs = Accounts.query.filter(Accounts.user_id == user_id).all()
            accounts = [{'id': str(a.id), 'name': a.name, 'account_type': a.account_type} for a in user_accs]

            try:
                from anthropic import Anthropic
                client = Anthropic()
                all_suggestions = []

                for batch_start in range(0, len(descriptions), _BATCH_SIZE):
                    batch = descriptions[batch_start:batch_start + _BATCH_SIZE]
                    prompt = _build_prompt(batch, categories, accounts)

                    message = client.messages.create(
                        model='claude-haiku-4-5-20251001',
                        max_tokens=2048,
                        messages=[{'role': 'user', 'content': prompt}]
                    )

                    raw = message.content[0].text.strip()
                    batch_result = json.loads(raw)

                    for s in batch_result.get('suggestions', []):
                        all_suggestions.append({
                            'index': s['index'] + batch_start,
                            'category_id': s.get('category_id'),
                            'opposing_account_id': s.get('opposing_account_id'),
                            'new_account': s.get('new_account'),
                        })

                return json_response({'suggestions': all_suggestions}, HttpCode.OK)

            except json.JSONDecodeError:
                return json_response('Réponse IA invalide (JSON malformé)', HttpCode.SERVER_ERROR)
            except Exception as e:
                return json_response(str(e), HttpCode.SERVER_ERROR)
