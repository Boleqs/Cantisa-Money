import csv
import io
import uuid
from datetime import datetime
from marshmallow import Schema, fields, ValidationError, validate
from sqlalchemy import func as sql_func

from flask import request, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PERMISSIONS_LIST)
from backend.utils.api_responses import json_response
from backend.utils.market_price import get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission

TRANSACTIONS_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']
BALANCE_TOLERANCE = 0.01


class SplitInputSchema(Schema):
    account_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True)
    description = fields.String(load_default=None)


class AddTransactionSchema(Schema):
    description = fields.String(load_default=None)
    post_date = fields.String(required=True)
    effective_date = fields.String(load_default=None)
    category_id = fields.UUID(load_default=None)
    is_cleared = fields.Boolean(load_default=False)
    splits = fields.List(fields.Nested(SplitInputSchema), required=True, validate=validate.Length(min=1))


class UpdateTransactionSchema(Schema):
    transaction_id = fields.UUID(required=True)
    description = fields.String(load_default=None)
    post_date = fields.String(required=True)
    effective_date = fields.String(load_default=None)
    category_id = fields.UUID(load_default=None)
    is_cleared = fields.Boolean(load_default=False)
    splits = fields.List(fields.Nested(SplitInputSchema), required=True, validate=validate.Length(min=1))


class GetTransactionsSchema(Schema):
    transaction_id = fields.UUID()
    account_id    = fields.UUID()
    page          = fields.Integer(load_default=1)
    per_page      = fields.Integer(load_default=50)
    search        = fields.String(load_default=None)
    is_cleared    = fields.Boolean(load_default=None)
    date_from     = fields.String(load_default=None)
    date_to       = fields.String(load_default=None)
    amount_min    = fields.Float(load_default=None)
    amount_max    = fields.Float(load_default=None)
    category_id   = fields.UUID(load_default=None)
    tag_id        = fields.UUID(load_default=None)


class DeleteTransactionSchema(Schema):
    transaction_id = fields.UUID(required=True)


class QuickFillSchema(Schema):
    q = fields.String(required=True, validate=validate.Length(min=1))


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, '%Y-%m-%d')


def _derive_tx_currency(Accounts, splits_data):
    """La transaction n'a plus de devise choisie par l'utilisateur : elle est prise sur le compte
    du premier split (même logique que les transactions générées automatiquement, cf. rt_assets.py
    et scheduler.py::_execute_subscription). Retourne (currency_id, error_response)."""
    account = Accounts.query.filter_by(id=splits_data[0]['account_id']).first()
    if not account:
        return None, json_response('Account not found', HttpCode.NOT_FOUND)
    return account.currency_id, None


def _resolve_split_fx_rates(Accounts, Commodities, FxRates, tx_currency_id, on_date, splits_data):
    """Pour chaque split, calcule le taux permettant de convertir son `quantity` (devise du compte du
    split) vers la devise de la transaction : valeur_en_devise_tx = quantity * fx_rate. Retourne
    (liste de (account_id, quantity, fx_rate), all_rates_resolved). Si un taux est introuvable
    (yfinance + cache indisponibles), on retombe sur 1.0 pour ce split et all_rates_resolved passe à
    False — la vérification d'équilibre est alors ignorée plutôt que de bloquer la saisie."""
    tx_commodity = Commodities.query.filter_by(id=tx_currency_id).first()
    tx_code = tx_commodity.short_name if tx_commodity else None

    account_ids = {s['account_id'] for s in splits_data}
    accounts_by_id = {a.id: a for a in Accounts.query.filter(Accounts.id.in_(account_ids)).all()}
    commodities_by_id = {c.id: c for c in Commodities.query.all()}

    resolved = []
    all_ok = True
    for s in splits_data:
        account = accounts_by_id.get(s['account_id'])
        account_commodity = commodities_by_id.get(account.currency_id) if account else None
        account_code = account_commodity.short_name if account_commodity else tx_code

        if not tx_code or not account_code or account_code == tx_code:
            fx_rate = 1.0
        else:
            fx_rate = get_fx_rate(account_code, tx_code, FxRates, on_date=on_date)
            if fx_rate is None:
                fx_rate = 1.0
                all_ok = False
        resolved.append((s['account_id'], s['quantity'], fx_rate, s.get('description')))
    return resolved, all_ok


def _tx_to_dict(tx, Splits, TagsOnSplits):
    # Ordre stable (débit d'abord) : le frontend traite le 1er split comme le compte "principal"
    # (devise de la transaction, cible des tags) — sans ORDER BY explicite, Postgres ne garantit
    # aucun ordre, ce qui ferait apparemment "changer" de compte principal à chaque rechargement.
    splits = Splits.query.filter(Splits.tx_id == tx.id).order_by(Splits.quantity).all()
    return {
        'id': str(tx.id),
        'user_id': str(tx.user_id),
        'currency_id': str(tx.currency_id),
        'post_date': tx.post_date.isoformat() if tx.post_date else None,
        'effective_date': tx.effective_date.isoformat() if tx.effective_date else None,
        'description': tx.description,
        'category_id': str(tx.category_id) if tx.category_id else None,
        'is_cleared': tx.is_cleared,
        'splits': [
            {
                'id': str(s.id),
                'account_id': str(s.account_id),
                'quantity': float(s.quantity),
                'description': s.description,
                'fx_rate': float(s.fx_rate) if s.fx_rate is not None else 1.0,
                'tag_ids': [
                    str(tos.tag_id)
                    for tos in TagsOnSplits.query.filter(TagsOnSplits.split_id == s.id).all()
                ],
                'is_reconciled': s.is_reconciled,
            }
            for s in splits
        ],
    }


def _apply_tx_filters(query, params, DB, Transactions, Splits, TagsOnSplits):
    """Applique les filtres communs sur une query Transactions."""
    if params.get('account_id'):
        query = query.join(Splits, Splits.tx_id == Transactions.id).filter(
            Splits.account_id == params['account_id']
        )
    if params.get('search'):
        query = query.filter(Transactions.description.ilike(f"%{params['search']}%"))
    if params.get('is_cleared') is not None:
        query = query.filter(Transactions.is_cleared == params['is_cleared'])
    if params.get('date_from'):
        query = query.filter(Transactions.post_date >= _parse_date(params['date_from']))
    if params.get('date_to'):
        query = query.filter(Transactions.post_date <= _parse_date(params['date_to']))
    if params.get('category_id'):
        query = query.filter(Transactions.category_id == params['category_id'])

    amount_min = params.get('amount_min')
    amount_max = params.get('amount_max')
    if amount_min is not None or amount_max is not None:
        sub = DB.session.query(Splits.tx_id)
        if amount_min is not None:
            sub = sub.filter(sql_func.abs(Splits.quantity) >= float(amount_min))
        if amount_max is not None:
            sub = sub.filter(sql_func.abs(Splits.quantity) <= float(amount_max))
        query = query.filter(Transactions.id.in_(sub))

    if params.get('tag_id') and TagsOnSplits:
        sub = (DB.session.query(Splits.tx_id)
               .join(TagsOnSplits, TagsOnSplits.split_id == Splits.id)
               .filter(TagsOnSplits.tag_id == params['tag_id']))
        query = query.filter(Transactions.id.in_(sub))

    return query


HEADERS = ['Date', 'Description', 'Catégorie', 'Compte', 'Contrepartie', 'Montant', 'Pointé']
KEYS    = ['date', 'description', 'categorie', 'compte', 'contrepartie', 'montant', 'pointe']


def _export_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=KEYS, delimiter=';', extrasaction='ignore')
    writer.writerow(dict(zip(KEYS, HEADERS)))
    for r in rows:
        writer.writerow({**r, 'montant': f"{r['montant']:.2f}".replace('.', ',')})
    resp = make_response(buf.getvalue().encode('utf-8-sig'))
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = 'attachment; filename="transactions.csv"'
    return resp


# Police coeur fpdf2 (Helvetica) limitée au latin-1 : les caractères hors de cette plage
# (€, tirets/guillemets typographiques, emoji...) font planter pdf.cell() avec une
# FPDFUnicodeEncodingException. On les translittère quand un équivalent existe, sinon on
# les remplace, plutôt que d'embarquer une police TTF Unicode pour ce besoin simple.
_PDF_CHAR_MAP = {
    '€': 'EUR', '’': "'", '‘': "'", '“': '"', '”': '"',
    '–': '-', '—': '-', '…': '...',
}


def _pdf_safe(text):
    text = str(text)
    for src, dst in _PDF_CHAR_MAP.items():
        text = text.replace(src, dst)
    return text.encode('latin-1', errors='replace').decode('latin-1')


def _export_pdf(rows, tx_count):
    from fpdf import FPDF

    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_margins(10, 10, 10)
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=12)

    # Title
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, 'Cantisa Money - Export transactions', ln=True)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, f'{tx_count} transaction(s) - {datetime.now().strftime("%d/%m/%Y %H:%M")}', ln=True)
    pdf.ln(3)

    # Column widths (landscape A4 = 277mm usable)
    col_w = [22, 62, 32, 44, 44, 24, 16]

    # Header row
    pdf.set_fill_color(30, 41, 59)
    pdf.set_text_color(200, 200, 210)
    pdf.set_font('Helvetica', 'B', 8)
    for i, h in enumerate(HEADERS):
        pdf.cell(col_w[i], 7, h, border=1, fill=True)
    pdf.ln()

    # Data rows
    pdf.set_text_color(30, 30, 30)
    fill = False
    for r in rows:
        pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(255, 255, 255)
        pdf.set_font('Helvetica', '', 7)
        montant = f"{r['montant']:.2f}".replace('.', ',')
        values = [r['date'], r['description'][:50], r['categorie'][:18],
                  r['compte'][:26], r['contrepartie'][:26], montant, r['pointe']]
        for i, v in enumerate(values):
            pdf.cell(col_w[i], 6, _pdf_safe(v), border=1, fill=True)
        pdf.ln()
        fill = not fill

    buf = io.BytesIO(bytes(pdf.output()))
    resp = make_response(buf.read())
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'attachment; filename="transactions.pdf"'
    return resp


class TransactionsRoutes:
    def __init__(self, app, DB, Transactions, Splits, TagsOnSplits, Users, Accounts=None, Categories=None,
                 Commodities=None, FxRates=None):
        ROUTE_PATH = f"{ROOT_PATH}/transactions"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, TRANSACTIONS_PERM)
        def get_transactions():
            try:
                data = GetTransactionsSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            if data.get('transaction_id'):
                tx = Transactions.query.filter(
                    Transactions.id == data.get('transaction_id'),
                    Transactions.user_id == get_jwt_identity()
                ).first()
                if not tx:
                    return json_response('Transaction not found', HttpCode.NOT_FOUND)
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.OK)

            query = Transactions.query.filter(Transactions.user_id == get_jwt_identity())
            query = _apply_tx_filters(query, data, DB, Transactions, Splits, TagsOnSplits)

            total = query.count()
            page = max(1, data.get('page', 1))
            per_page = min(max(1, data.get('per_page', 50)), 200)
            pages = max(1, (total + per_page - 1) // per_page)
            txs = (query.order_by(Transactions.post_date.desc())
                   .offset((page - 1) * per_page)
                   .limit(per_page)
                   .all())
            return json_response({
                'transactions': [_tx_to_dict(tx, Splits, TagsOnSplits) for tx in txs],
                'total': total,
                'page': page,
                'per_page': per_page,
                'pages': pages,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, TRANSACTIONS_PERM)
        def add_transaction():
            try:
                data = AddTransactionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)
            post_date = _parse_date(data['post_date'])
            currency_id, error = _derive_tx_currency(Accounts, data['splits'])
            if error:
                return error
            fx_rates_resolved, all_ok = _resolve_split_fx_rates(
                Accounts, Commodities, FxRates, currency_id, post_date.date(), data['splits'])
            if all_ok:
                total = sum(float(qty) * fx_rate for _, qty, fx_rate, _ in fx_rates_resolved)
                if abs(total) > BALANCE_TOLERANCE:
                    return json_response(
                        f"Les splits ne s'équilibrent pas une fois convertis dans la devise de la transaction (écart : {round(total, 2)})",
                        HttpCode.BAD_REQUEST)
            try:
                tx = Transactions(
                    user_id=get_jwt_identity(),
                    currency_id=currency_id,
                    post_date=post_date,
                    effective_date=_parse_date(data.get('effective_date')) or post_date,
                    description=data.get('description'),
                    category_id=data.get('category_id'),
                    is_cleared=data.get('is_cleared', False),
                )
                DB.session.add(tx)
                DB.session.flush()
                for account_id, quantity, fx_rate, description in fx_rates_resolved:
                    DB.session.add(Splits(
                        tx_id=tx.id,
                        account_id=account_id,
                        quantity=quantity,
                        fx_rate=fx_rate,
                        description=description,
                    ))
                DB.session.commit()
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, TRANSACTIONS_PERM)
        def update_transaction():
            try:
                data = UpdateTransactionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            tx = Transactions.query.filter(
                Transactions.id == data['transaction_id'],
                Transactions.user_id == get_jwt_identity()
            ).first()
            if not tx:
                return json_response('Transaction not found', HttpCode.NOT_FOUND)

            post_date = _parse_date(data['post_date'])
            currency_id, error = _derive_tx_currency(Accounts, data['splits'])
            if error:
                return error
            fx_rates_resolved, all_ok = _resolve_split_fx_rates(
                Accounts, Commodities, FxRates, currency_id, post_date.date(), data['splits'])
            if all_ok:
                total = sum(float(qty) * fx_rate for _, qty, fx_rate, _ in fx_rates_resolved)
                if abs(total) > BALANCE_TOLERANCE:
                    return json_response(
                        f"Les splits ne s'équilibrent pas une fois convertis dans la devise de la transaction (écart : {round(total, 2)})",
                        HttpCode.BAD_REQUEST)
            try:
                tx.currency_id = currency_id
                tx.post_date = post_date
                tx.effective_date = _parse_date(data.get('effective_date')) or post_date
                tx.description = data.get('description')
                tx.category_id = data.get('category_id')
                tx.is_cleared = data.get('is_cleared', False)

                # Les tags (TagsOnSplits, ON DELETE CASCADE) et le pointage sont attachés aux splits ;
                # comme les splits sont entièrement recréés à chaque modification (pas de colonne
                # stable permettant de les mettre à jour en place), on capture cet état par compte
                # avant suppression pour le réappliquer aux nouveaux splits du même compte.
                old_splits = Splits.query.filter(Splits.tx_id == tx.id).all()
                tags_by_account = {}
                reconciled_accounts = set()
                for s in old_splits:
                    tag_ids = [t.tag_id for t in TagsOnSplits.query.filter(TagsOnSplits.split_id == s.id).all()]
                    if tag_ids:
                        tags_by_account.setdefault(str(s.account_id), set()).update(tag_ids)
                    if s.is_reconciled:
                        reconciled_accounts.add(str(s.account_id))

                Splits.query.filter(Splits.tx_id == tx.id).delete()
                for account_id, quantity, fx_rate, description in fx_rates_resolved:
                    new_split = Splits(
                        tx_id=tx.id,
                        account_id=account_id,
                        quantity=quantity,
                        fx_rate=fx_rate,
                        description=description,
                        is_reconciled=str(account_id) in reconciled_accounts,
                    )
                    DB.session.add(new_split)
                    DB.session.flush()
                    for tag_id in tags_by_account.get(str(account_id), ()):
                        DB.session.add(TagsOnSplits(split_id=new_split.id, tag_id=tag_id))

                DB.session.commit()
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, TRANSACTIONS_PERM)
        def delete_transaction():
            try:
                data = DeleteTransactionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            tx = Transactions.query.filter(
                Transactions.id == data['transaction_id'],
                Transactions.user_id == get_jwt_identity()
            ).first()
            if not tx:
                return json_response('Transaction not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(tx)
                DB.session.commit()
                return json_response('Transaction deleted', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/quickfill", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, TRANSACTIONS_PERM)
        def quickfill_transactions():
            """Saisie rapide façon 'Quick Fill' : à partir d'un préfixe de description déjà tapé,
            propose les transactions passées correspondantes (la plus récente par libellé distinct)
            pour pré-remplir catégorie/compte/montant sans ressaisir une transaction récurrente."""
            try:
                data = QuickFillSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            q = data['q'].strip()
            if not q:
                return json_response([], HttpCode.OK)

            txs = (Transactions.query
                   .filter(Transactions.user_id == user_id, Transactions.description.ilike(f'{q}%'))
                   .order_by(Transactions.post_date.desc())
                   .limit(50).all())

            seen = set()
            suggestions = []
            for tx in txs:
                if not tx.description:
                    continue
                key = tx.description.strip().lower()
                if key in seen:
                    continue
                seen.add(key)
                splits = Splits.query.filter(Splits.tx_id == tx.id).order_by(Splits.quantity).all()
                suggestion = {
                    'description': tx.description,
                    'category_id': str(tx.category_id) if tx.category_id else None,
                }
                # Même convention que l'export (source = split négatif) : seules les transactions
                # simples à 2 splits peuvent être reconstruites en "montant + compte source/destination"
                # pour le mode simple du formulaire — les splits multiples ne sont pas pré-remplissables.
                if len(splits) == 2:
                    source = next((s for s in splits if s.quantity < 0), splits[0])
                    dest = next(s for s in splits if s is not source)
                    suggestion['from_account_id'] = str(source.account_id)
                    suggestion['to_account_id'] = str(dest.account_id)
                    suggestion['amount'] = abs(float(source.quantity))
                suggestions.append(suggestion)
                if len(suggestions) >= 8:
                    break
            return json_response(suggestions, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/export", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, TRANSACTIONS_PERM)
        def export_transactions():
            user_id = get_jwt_identity()
            fmt = request.args.get('format', 'csv').lower()
            # 'format' n'est pas un champ du schéma de filtres : le laisser dans les args fait
            # échouer la validation (Unknown field) et retombait silencieusement sur params = {},
            # c'est-à-dire un export non filtré malgré des filtres actifs côté client.
            filter_args = request.args.to_dict()
            filter_args.pop('format', None)
            try:
                params = GetTransactionsSchema().load(filter_args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            query = Transactions.query.filter(Transactions.user_id == user_id)
            query = _apply_tx_filters(query, params, DB, Transactions, Splits, TagsOnSplits)
            txs = query.order_by(Transactions.post_date.desc()).limit(10000).all()

            # Lookup maps for names
            acc_map, cat_map = {}, {}
            if Accounts:
                acc_map = {str(a.id): a.name for a in Accounts.query.filter_by(user_id=user_id).all()}
            if Categories:
                cat_map = {str(c.id): c.name for c in Categories.query.filter_by(user_id=user_id).all()}

            # Une ligne par transaction (pas par split) : en comptabilité en partie double, une
            # transaction simple a 2 splits (compte source débité / compte destination crédité,
            # cf. TransactionModal.vue) — les aplatir en 2 lignes ferait apparaître le même
            # virement/paiement deux fois dans l'export. On retient le split "source" (négatif)
            # comme montant/compte principal et on liste la contrepartie à part.
            rows = []
            for tx in txs:
                splits = Splits.query.filter(Splits.tx_id == tx.id).all()
                if not splits:
                    continue
                cat_name = cat_map.get(str(tx.category_id), '') if tx.category_id else ''
                date_str = tx.post_date.strftime('%d/%m/%Y') if tx.post_date else ''
                cleared = 'Oui' if tx.is_cleared else 'Non'

                # Filtré par compte : on affiche le montant/compte du point de vue de ce compte
                # précis (même logique que AccountDetail.vue), pas toujours le split "source".
                filtered_split = None
                if params.get('account_id'):
                    filtered_split = next(
                        (s for s in splits if str(s.account_id) == str(params['account_id'])), None)

                if filtered_split:
                    others = [s for s in splits if s is not filtered_split]
                    montant = float(filtered_split.quantity)
                    compte = acc_map.get(str(filtered_split.account_id), str(filtered_split.account_id))
                    contrepartie = ', '.join(
                        acc_map.get(str(s.account_id), str(s.account_id)) for s in others
                    ) or '—'
                elif len(splits) == 2:
                    source = next((s for s in splits if s.quantity < 0), splits[0])
                    dest = next(s for s in splits if s is not source)
                    montant = float(source.quantity)
                    compte = acc_map.get(str(source.account_id), str(source.account_id))
                    contrepartie = acc_map.get(str(dest.account_id), str(dest.account_id))
                else:
                    # Splits manuels/multi-comptes (mode avancé) : pas de source/destination unique
                    # -> 1er split (même convention que _tx_to_dict) comme compte principal, le
                    # reste listé comme contrepartie.
                    primary, others = splits[0], splits[1:]
                    montant = float(primary.quantity)
                    compte = acc_map.get(str(primary.account_id), str(primary.account_id))
                    contrepartie = ', '.join(
                        acc_map.get(str(s.account_id), str(s.account_id)) for s in others
                    ) or '—'

                rows.append({
                    'date': date_str,
                    'description': tx.description or '',
                    'categorie': cat_name,
                    'compte': compte,
                    'contrepartie': contrepartie,
                    'montant': montant,
                    'pointe': cleared,
                })

            if fmt == 'csv':
                return _export_csv(rows)
            elif fmt == 'pdf':
                return _export_pdf(rows, len(txs))
            return json_response('Format non supporté (csv ou pdf)', HttpCode.BAD_REQUEST)
