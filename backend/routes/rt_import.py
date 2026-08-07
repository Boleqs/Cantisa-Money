import csv
import io
import re
import unicodedata
from datetime import datetime
from marshmallow import Schema, fields, ValidationError

from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PERMISSIONS_LIST)
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

IMPORT_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']

DATE_FORMATS = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d/%m/%y', '%Y/%m/%d', '%m/%d/%y']

# Longueur minimale d'un mot-clé normalisé pour être mémorisé/utilisé comme règle — évite qu'un
# libellé trop court ou vidé par la normalisation (ex: uniquement des chiffres) ne matche tout.
MIN_RULE_KEYWORD_LENGTH = 3


def normalize_description(desc):
    """Normalise un libellé de transaction en clé de règle stable : minuscules, sans accents, sans
    chiffres (numéros de référence, dates) ni ponctuation — deux occurrences de la même transaction
    récurrente (ex: "CB CARREFOUR 05/08" et "CB CARREFOUR 12/09") normalisent vers la même clé."""
    if not desc:
        return ''
    s = unicodedata.normalize('NFKD', desc)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r'\d+', ' ', s)
    s = re.sub(r'[^a-z\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _match_rule(rules_by_keyword, description):
    """Cherche une règle de catégorisation apprise pour ce libellé. Retourne (category_id,
    opposing_account_id), chacun pouvant être None si la règle ne renseigne pas ce champ."""
    key = normalize_description(description)
    if not key or len(key) < MIN_RULE_KEYWORD_LENGTH:
        return None, None
    rule = rules_by_keyword.get(key)
    if not rule:
        return None, None
    return (str(rule.category_id) if rule.category_id else None,
            str(rule.opposing_account_id) if rule.opposing_account_id else None)


class ConfirmImportSchema(Schema):
    account_id = fields.UUID(required=True)
    expense_opposing_account_id = fields.UUID(required=True)
    income_opposing_account_id = fields.UUID(required=True)
    currency_id = fields.UUID(required=True)
    transactions = fields.List(fields.Dict(), required=True)


def _parse_amount(raw, decimal_sep):
    raw = raw.strip().replace(' ', '').replace('\xa0', '').replace('\u202f', '')
    if not raw:
        raise ValueError("Montant vide")
    if decimal_sep == ',':
        # French format: 1.234,56 → remove thousands dot, swap decimal comma
        raw = raw.replace('.', '').replace(',', '.')
    else:
        # US/QIF format: 1,234.56 → remove thousands comma
        raw = raw.replace(',', '')
    return float(raw)


def _parse_date(date_str, preferred_format):
    # QIF sometimes uses D with a dash: "1/ 5'26" or "01/05/2026"
    date_str = date_str.strip().replace("'", '/').replace(' ', '')
    formats = [preferred_format] + [f for f in DATE_FORMATS if f != preferred_format]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Date non reconnue : {date_str!r}")


QIF_TYPE_MAP = {
    'bank':    'Current',
    'cash':    'Current',
    'ccard':   'Current',
    'invst':   'Assets',
    'mutual':  'Assets',
    'oth a':   'Assets',
    'oth l':   'Assets',
    'invoice': 'Assets',
    'income':  'Income',
    'expense': 'Expense',
}


def _detect_format(content):
    """Return 'qif' if file looks like QIF, else 'csv'."""
    if content.lstrip().startswith('!'):
        return 'qif'
    return 'csv'


def _parse_qif(content, date_format, decimal_sep, account_id, user_id, Transactions, Splits, Categories, DB, rules_by_keyword):
    """Parse QIF content, return (transactions, errors, accounts_found).

    accounts_found: list of {name, qif_type, cantisa_type, description}
    transactions: each entry may include qif_account (name of the source QIF account)
    """
    parsed = []
    errors = []
    accounts_found = []
    seen_account_names = set()

    # Catégorie (champ L) : matchée par nom (insensible à la casse) sur les catégories
    # existantes de l'utilisateur, sinon créée à la volée. "[Nom]" désigne un virement
    # vers un autre compte QIF, pas une vraie catégorie — ignoré.
    category_cache = {c.name.strip().lower(): c.id for c in Categories.query.filter_by(user_id=user_id).all()}

    def resolve_category(name):
        if not name:
            return None
        name = name.strip()
        if not name or (name.startswith('[') and name.endswith(']')):
            return None
        key = name.lower()
        if key in category_cache:
            return category_cache[key]
        new_cat = Categories(user_id=user_id, name=name)
        DB.session.add(new_cat)
        DB.session.flush()
        category_cache[key] = new_cat.id
        return new_cat.id

    current_tx = {}
    current_acc_def = {}
    current_qif_account = None  # name of the active !Account section
    in_account_def = False
    row_idx = 0

    for line in content.splitlines():
        line = line.rstrip('\r')
        if not line:
            continue
        tag = line[0]
        value = line[1:]

        # ── Directive line (!Account, !Type:Bank, …) ──────────────────────
        if tag == '!':
            directive = value.strip().lower()
            if directive == 'account':
                in_account_def = True
                current_acc_def = {}
            else:
                # !Type:xxx — end of account definition section, start transactions
                in_account_def = False
            continue

        # ── Account definition block ───────────────────────────────────────
        if in_account_def:
            if tag == '^':
                name = current_acc_def.get('name')
                if name and name not in seen_account_names:
                    seen_account_names.add(name)
                    qif_type = current_acc_def.get('type', '')
                    accounts_found.append({
                        'name': name,
                        'qif_type': qif_type,
                        'cantisa_type': QIF_TYPE_MAP.get(qif_type.lower(), 'Current'),
                        'description': current_acc_def.get('description', ''),
                    })
                    current_qif_account = name
                in_account_def = False
                current_acc_def = {}
            elif tag == 'N':
                current_acc_def['name'] = value.strip()
            elif tag == 'T':
                current_acc_def['type'] = value.strip()
            elif tag == 'D':
                current_acc_def['description'] = value.strip()
            continue

        # ── Transaction record ─────────────────────────────────────────────
        if tag == '^':
            if 'date' in current_tx and 'amount' in current_tx:
                try:
                    tx_date = _parse_date(current_tx['date'], date_format)
                    amount = _parse_amount(current_tx['amount'], decimal_sep)
                    desc = current_tx.get('payee') or current_tx.get('memo') or ''

                    is_duplicate = False
                    if account_id:
                        existing = Splits.query.join(
                            Transactions, Transactions.id == Splits.tx_id
                        ).filter(
                            Transactions.user_id == user_id,
                            Splits.account_id == account_id,
                            Transactions.post_date == tx_date,
                            Splits.quantity == amount,
                        ).first()
                        is_duplicate = existing is not None

                    # Le champ QIF (catégorie explicite du fichier) est prioritaire ; la règle
                    # apprise ne comble que ce que le fichier ne renseigne pas.
                    category_id = resolve_category(current_tx.get('category'))
                    rule_category_id, rule_opposing_id = _match_rule(rules_by_keyword, desc)
                    parsed.append({
                        'row': row_idx,
                        'date': tx_date.strftime('%Y-%m-%d'),
                        'description': desc,
                        'amount': amount,
                        'category_id': category_id or rule_category_id,
                        'opposing_account_id': rule_opposing_id,
                        'qif_account': current_qif_account,
                        'is_duplicate': is_duplicate,
                        'selected': not is_duplicate,
                    })
                except Exception as e:
                    errors.append({'row': row_idx, 'error': str(e), 'raw': list(current_tx.values())})
            current_tx = {}
            row_idx += 1
        elif tag == 'D':
            current_tx['date'] = value
        elif tag in ('T', 'U'):
            if 'amount' not in current_tx or tag == 'T':
                current_tx['amount'] = value
        elif tag == 'P':
            current_tx['payee'] = value.strip()
        elif tag == 'M':
            current_tx['memo'] = value.strip()
        elif tag == 'L':
            current_tx['category'] = value.strip()

    # Flush last record if file doesn't end with ^
    if 'date' in current_tx and 'amount' in current_tx:
        try:
            tx_date = _parse_date(current_tx['date'], date_format)
            amount = _parse_amount(current_tx['amount'], decimal_sep)
            desc = current_tx.get('payee') or current_tx.get('memo') or ''
            category_id = resolve_category(current_tx.get('category'))
            rule_category_id, rule_opposing_id = _match_rule(rules_by_keyword, desc)
            parsed.append({
                'row': row_idx,
                'date': tx_date.strftime('%Y-%m-%d'),
                'description': desc,
                'amount': amount,
                'category_id': category_id or rule_category_id,
                'opposing_account_id': rule_opposing_id,
                'qif_account': current_qif_account,
                'is_duplicate': False,
                'selected': True,
            })
        except Exception:
            pass

    return parsed, errors, accounts_found


class ImportRoutes:
    def __init__(self, app, DB, Transactions, Splits, Users, Categories, ImportCategoryRules):
        ROUTE_PATH = f"{ROOT_PATH}/import"

        @app.route(f"{ROUTE_PATH}/parse", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, IMPORT_PERM)
        def parse_import():
            file = request.files.get('file')
            if not file:
                return json_response('Aucun fichier fourni', HttpCode.NOT_FOUND)

            # Read with BOM handling and Latin-1 fallback
            try:
                content = file.stream.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                file.stream.seek(0)
                content = file.stream.read().decode('latin-1')

            date_format = request.form.get('date_format', '%d/%m/%Y')
            decimal_sep = request.form.get('decimal_sep', ',')
            account_id = request.form.get('account_id') or None
            user_id = get_jwt_identity()

            # Règles de catégorisation apprises lors de confirmations d'imports précédentes (voir
            # confirm_import ci-dessous) — remplacent la catégorisation par IA.
            rules_by_keyword = {
                r.keyword: r for r in ImportCategoryRules.query.filter_by(user_id=user_id).all()
            }

            # Auto-detect or honour explicit format
            fmt = request.form.get('format') or _detect_format(content)

            # ── QIF ──────────────────────────────────────────────────────────
            if fmt == 'qif':
                parsed, errors, accounts_found = _parse_qif(
                    content, date_format, decimal_sep,
                    account_id, user_id, Transactions, Splits, Categories, DB, rules_by_keyword
                )
                # Persiste les catégories créées à la volée pendant le parsing.
                DB.session.commit()
                return json_response({
                    'format': 'qif',
                    'headers': [],
                    'preview': [],
                    'transactions': parsed,
                    'errors': errors,
                    'accounts_found': accounts_found,
                }, HttpCode.OK)

            # ── CSV ───────────────────────────────────────────────────────────
            delimiter = request.form.get('delimiter', ';')
            if delimiter == '\\t':
                delimiter = '\t'
            has_header = request.form.get('has_header', 'true').lower() == 'true'
            date_col = int(request.form.get('date_col', 0))
            desc_col = int(request.form.get('desc_col', 1))

            amount_col_raw = request.form.get('amount_col', '')
            debit_col_raw = request.form.get('debit_col', '')
            credit_col_raw = request.form.get('credit_col', '')
            amount_col = int(amount_col_raw) if amount_col_raw != '' else None
            debit_col = int(debit_col_raw) if debit_col_raw != '' else None
            credit_col = int(credit_col_raw) if credit_col_raw != '' else None

            reader = csv.reader(io.StringIO(content), delimiter=delimiter)
            rows = list(reader)

            if not rows:
                return json_response({
                    'format': 'csv',
                    'headers': [], 'preview': [], 'transactions': [], 'errors': []
                }, HttpCode.OK)

            if has_header:
                headers = rows[0]
                data_rows = rows[1:]
            else:
                headers = [str(i) for i in range(len(rows[0]))]
                data_rows = rows

            preview = [list(row) for row in data_rows[:5]]
            parsed = []
            errors = []

            for i, row in enumerate(data_rows):
                if not any(cell.strip() for cell in row):
                    continue
                try:
                    date_str = row[date_col].strip() if date_col < len(row) else ''
                    tx_date = _parse_date(date_str, date_format)
                    desc = row[desc_col].strip() if desc_col < len(row) else ''

                    if amount_col is not None:
                        amount = _parse_amount(row[amount_col] if amount_col < len(row) else '', decimal_sep)
                    elif debit_col is not None and credit_col is not None:
                        d_raw = row[debit_col] if debit_col < len(row) else ''
                        c_raw = row[credit_col] if credit_col < len(row) else ''
                        debit = _parse_amount(d_raw, decimal_sep) if d_raw.strip() else 0.0
                        credit = _parse_amount(c_raw, decimal_sep) if c_raw.strip() else 0.0
                        amount = credit - debit
                    else:
                        raise ValueError("Aucune colonne de montant configurée")

                    is_duplicate = False
                    if account_id:
                        existing = Splits.query.join(
                            Transactions, Transactions.id == Splits.tx_id
                        ).filter(
                            Transactions.user_id == user_id,
                            Splits.account_id == account_id,
                            Transactions.post_date == tx_date,
                            Splits.quantity == amount,
                        ).first()
                        is_duplicate = existing is not None

                    rule_category_id, rule_opposing_id = _match_rule(rules_by_keyword, desc)
                    parsed.append({
                        'row': i,
                        'date': tx_date.strftime('%Y-%m-%d'),
                        'description': desc,
                        'amount': amount,
                        'category_id': rule_category_id,
                        'opposing_account_id': rule_opposing_id,
                        'is_duplicate': is_duplicate,
                        'selected': not is_duplicate,
                    })
                except (IndexError, ValueError) as e:
                    errors.append({'row': i, 'error': str(e), 'raw': list(row)})

            return json_response({
                'format': 'csv',
                'headers': headers,
                'preview': preview,
                'transactions': parsed,
                'errors': errors,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/confirm", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, IMPORT_PERM)
        def confirm_import():
            try:
                data = ConfirmImportSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            user_id = get_jwt_identity()
            account_id = data['account_id']
            expense_opposing_account_id = data['expense_opposing_account_id']
            income_opposing_account_id = data['income_opposing_account_id']
            currency_id = data['currency_id']

            created = 0
            skipped = 0

            try:
                for tx_data in data['transactions']:
                    if not tx_data.get('selected', True):
                        skipped += 1
                        continue

                    tx_date = datetime.strptime(tx_data['date'], '%Y-%m-%d')
                    amount = float(tx_data['amount'])
                    # Contrepartie par défaut selon le signe (dépense/recette), sauf
                    # override par transaction (choix manuel ou suggestion d'une règle apprise).
                    default_opposing = expense_opposing_account_id if amount < 0 else income_opposing_account_id
                    tx_opposing = tx_data.get('opposing_account_id') or default_opposing
                    category_id = tx_data.get('category_id') or None

                    tx = Transactions(
                        user_id=user_id,
                        currency_id=currency_id,
                        post_date=tx_date,
                        effective_date=tx_date,
                        description=tx_data.get('description', ''),
                        is_cleared=True,
                        category_id=category_id,
                    )
                    DB.session.add(tx)
                    DB.session.flush()

                    DB.session.add(Splits(tx_id=tx.id, account_id=account_id, quantity=amount))
                    DB.session.add(Splits(tx_id=tx.id, account_id=tx_opposing, quantity=-amount))
                    created += 1

                    # Apprentissage de règle : mémorise la catégorie/contrepartie choisie pour ce
                    # libellé, réappliquée automatiquement aux imports futurs (voir parse_import).
                    # La contrepartie n'est mémorisée que si elle diffère de la contrepartie par
                    # défaut du moment, sinon celle-ci serait figée comme règle pour tout le monde.
                    explicit_opposing = tx_data.get('opposing_account_id') or None
                    learned_opposing = (explicit_opposing
                                        if explicit_opposing and str(explicit_opposing) != str(default_opposing)
                                        else None)
                    keyword = normalize_description(tx_data.get('description', ''))
                    if keyword and len(keyword) >= MIN_RULE_KEYWORD_LENGTH and (category_id or learned_opposing):
                        rule = ImportCategoryRules.query.filter_by(user_id=user_id, keyword=keyword).first()
                        if rule:
                            if category_id:
                                rule.category_id = category_id
                            if learned_opposing:
                                rule.opposing_account_id = learned_opposing
                            rule.updated_at = datetime.now()
                        else:
                            DB.session.add(ImportCategoryRules(
                                user_id=user_id, keyword=keyword,
                                category_id=category_id, opposing_account_id=learned_opposing,
                            ))

                DB.session.commit()
                return json_response({'created': created, 'skipped': skipped}, HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)