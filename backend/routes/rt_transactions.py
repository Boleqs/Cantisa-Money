import csv
import io
import uuid
from datetime import datetime
from marshmallow import Schema, fields, ValidationError
from sqlalchemy import func as sql_func

from flask import request, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH)
from backend.utils.api_responses import json_response


class SplitInputSchema(Schema):
    account_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True)


class AddTransactionSchema(Schema):
    description = fields.String(load_default=None)
    currency_id = fields.UUID(required=True)
    post_date = fields.String(required=True)
    effective_date = fields.String(load_default=None)
    category_id = fields.UUID(load_default=None)
    is_cleared = fields.Boolean(load_default=False)
    splits = fields.List(fields.Nested(SplitInputSchema), required=True)


class UpdateTransactionSchema(Schema):
    transaction_id = fields.UUID(required=True)
    description = fields.String(load_default=None)
    currency_id = fields.UUID(required=True)
    post_date = fields.String(required=True)
    effective_date = fields.String(load_default=None)
    category_id = fields.UUID(load_default=None)
    is_cleared = fields.Boolean(load_default=False)
    splits = fields.List(fields.Nested(SplitInputSchema), required=True)


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


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, '%Y-%m-%d')


def _tx_to_dict(tx, Splits, TagsOnSplits):
    splits = Splits.query.filter(Splits.tx_id == tx.id).all()
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


HEADERS = ['Date', 'Description', 'Catégorie', 'Compte', 'Montant', 'Pointé']
KEYS    = ['date', 'description', 'categorie', 'compte', 'montant', 'pointe']


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
    col_w = [24, 80, 36, 60, 26, 18]

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
        values = [r['date'], r['description'][:55], r['categorie'][:22],
                  r['compte'][:38], montant, r['pointe']]
        for i, v in enumerate(values):
            pdf.cell(col_w[i], 6, str(v), border=1, fill=True)
        pdf.ln()
        fill = not fill

    buf = io.BytesIO(bytes(pdf.output()))
    resp = make_response(buf.read())
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'attachment; filename="transactions.pdf"'
    return resp


class TransactionsRoutes:
    def __init__(self, app, DB, Transactions, Splits, TagsOnSplits, Accounts=None, Categories=None):
        ROUTE_PATH = f"{ROOT_PATH}/transactions"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
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
        def add_transaction():
            try:
                data = AddTransactionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)
            try:
                post_date = _parse_date(data['post_date'])
                tx = Transactions(
                    user_id=get_jwt_identity(),
                    currency_id=data['currency_id'],
                    post_date=post_date,
                    effective_date=_parse_date(data.get('effective_date')) or post_date,
                    description=data.get('description'),
                    category_id=data.get('category_id'),
                    is_cleared=data.get('is_cleared', False),
                )
                DB.session.add(tx)
                DB.session.flush()
                for split in data['splits']:
                    DB.session.add(Splits(
                        tx_id=tx.id,
                        account_id=split['account_id'],
                        quantity=split['quantity'],
                    ))
                DB.session.commit()
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
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
            try:
                post_date = _parse_date(data['post_date'])
                tx.currency_id = data['currency_id']
                tx.post_date = post_date
                tx.effective_date = _parse_date(data.get('effective_date')) or post_date
                tx.description = data.get('description')
                tx.category_id = data.get('category_id')
                tx.is_cleared = data.get('is_cleared', False)
                Splits.query.filter(Splits.tx_id == tx.id).delete()
                for split in data['splits']:
                    DB.session.add(Splits(
                        tx_id=tx.id,
                        account_id=split['account_id'],
                        quantity=split['quantity'],
                    ))
                DB.session.commit()
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
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

        @app.route(f"{ROUTE_PATH}/export", methods=['GET'])
        @jwt_required()
        def export_transactions():
            user_id = get_jwt_identity()
            fmt = request.args.get('format', 'csv').lower()
            try:
                params = GetTransactionsSchema().load(request.args)
            except ValidationError:
                params = {}

            query = Transactions.query.filter(Transactions.user_id == user_id)
            query = _apply_tx_filters(query, params, DB, Transactions, Splits, TagsOnSplits)
            txs = query.order_by(Transactions.post_date.desc()).limit(10000).all()

            # Lookup maps for names
            acc_map, cat_map = {}, {}
            if Accounts:
                acc_map = {str(a.id): a.name for a in Accounts.query.filter_by(user_id=user_id).all()}
            if Categories:
                cat_map = {str(c.id): c.name for c in Categories.query.filter_by(user_id=user_id).all()}

            # Flatten: one row per split
            rows = []
            for tx in txs:
                splits = Splits.query.filter(Splits.tx_id == tx.id).all()
                cat_name = cat_map.get(str(tx.category_id), '') if tx.category_id else ''
                date_str = tx.post_date.strftime('%d/%m/%Y') if tx.post_date else ''
                cleared = 'Oui' if tx.is_cleared else 'Non'
                for sp in splits:
                    rows.append({
                        'date': date_str,
                        'description': tx.description or '',
                        'categorie': cat_name,
                        'compte': acc_map.get(str(sp.account_id), str(sp.account_id)),
                        'montant': float(sp.quantity),
                        'pointe': cleared,
                    })

            if fmt == 'csv':
                return _export_csv(rows)
            elif fmt == 'pdf':
                return _export_pdf(rows, len(txs))
            return json_response('Format non supporté (csv ou pdf)', HttpCode.BAD_REQUEST)
