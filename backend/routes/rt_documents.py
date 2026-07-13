from datetime import datetime
from marshmallow import Schema, fields, ValidationError

from flask import request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import (HttpCode,
                            VAR_API_ROOT_PATH as ROOT_PATH,
                            VAR_PERMISSIONS_LIST)
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.receipt_ocr import extract_text, parse_receipt
from backend.routes.rt_transactions import _tx_to_dict

DOCUMENTS_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']

ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}


class ConfirmDocumentSchema(Schema):
    document_id = fields.UUID(required=True)
    account_id = fields.UUID(required=True)           # compte payeur (ex: Compte Courant)
    expense_account_id = fields.UUID(required=True)   # compte de dépense pour toutes les lignes
    category_id = fields.UUID(load_default=None)
    description = fields.String(load_default=None)
    post_date = fields.String(required=True)
    lines = fields.List(fields.Dict(), required=True)


class DocumentsRoutes:
    def __init__(self, app, DB, TransactionDocuments, Transactions, Splits, TagsOnSplits, Tags, Accounts, Users):
        ROUTE_PATH = f"{ROOT_PATH}/documents"

        @app.route(f"{ROUTE_PATH}/parse", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, DOCUMENTS_PERM)
        def parse_document():
            file = request.files.get('file')
            if not file:
                return json_response('Aucun fichier fourni', HttpCode.NOT_FOUND)

            mime_type = file.mimetype
            if mime_type not in ALLOWED_MIME_TYPES:
                return json_response(f"Format non supporté : {mime_type}", HttpCode.BAD_REQUEST)

            file_bytes = file.stream.read()
            user_id = get_jwt_identity()

            try:
                raw_text = extract_text(file_bytes, mime_type)
            except Exception as e:
                return json_response(f"Erreur OCR : {e}", HttpCode.SERVER_ERROR)

            user_tags = [{'id': str(t.id), 'name': t.name}
                         for t in Tags.query.filter(Tags.user_id == user_id).all()]
            parsed = parse_receipt(raw_text, user_tags)

            doc = TransactionDocuments(
                user_id=user_id,
                original_filename=file.filename,
                mime_type=mime_type,
                file_data=file_bytes,
                status='pending',
            )
            DB.session.add(doc)
            DB.session.commit()

            return json_response({
                'document_id': str(doc.id),
                'merchant': parsed['merchant'],
                'date': parsed['date'],
                'total': parsed['total'],
                'lines': parsed['lines'],
                'warnings': parsed['warnings'],
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/confirm", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, DOCUMENTS_PERM)
        def confirm_document():
            try:
                data = ConfirmDocumentSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.NOT_FOUND)

            user_id = get_jwt_identity()
            doc = TransactionDocuments.query.filter(
                TransactionDocuments.id == data['document_id'],
                TransactionDocuments.user_id == user_id,
            ).first()
            if not doc:
                return json_response('Document introuvable', HttpCode.NOT_FOUND)
            if doc.status != 'pending':
                return json_response('Document déjà confirmé', HttpCode.CONFLICT)

            account = Accounts.query.filter(
                Accounts.id == data['account_id'], Accounts.user_id == user_id
            ).first()
            if not account:
                return json_response('Compte payeur introuvable', HttpCode.NOT_FOUND)

            lines = data['lines']
            if not lines:
                return json_response('Aucune ligne à enregistrer', HttpCode.BAD_REQUEST)

            try:
                total = sum(float(line['amount']) for line in lines)
                post_date = datetime.strptime(data['post_date'], '%Y-%m-%d')

                tx = Transactions(
                    user_id=user_id,
                    currency_id=account.currency_id,
                    post_date=post_date,
                    effective_date=post_date,
                    description=data.get('description') or doc.original_filename,
                    category_id=data.get('category_id'),
                    is_cleared=False,
                )
                DB.session.add(tx)
                DB.session.flush()

                DB.session.add(Splits(tx_id=tx.id, account_id=account.id, quantity=-total))
                for line in lines:
                    split = Splits(
                        tx_id=tx.id,
                        account_id=data['expense_account_id'],
                        quantity=float(line['amount']),
                        description=line.get('label') or None,
                    )
                    DB.session.add(split)
                    DB.session.flush()
                    if line.get('tag_id'):
                        DB.session.add(TagsOnSplits(split_id=split.id, tag_id=line['tag_id']))

                doc.tx_id = tx.id
                doc.status = 'confirmed'

                DB.session.commit()
                return json_response(_tx_to_dict(tx, Splits, TagsOnSplits), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/attach", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, DOCUMENTS_PERM)
        def attach_document():
            """Joint un fichier (photo/PDF) à une transaction déjà existante — sans OCR ni
            création de splits, juste un justificatif rattaché après coup."""
            file = request.files.get('file')
            if not file:
                return json_response('Aucun fichier fourni', HttpCode.NOT_FOUND)

            mime_type = file.mimetype
            if mime_type not in ALLOWED_MIME_TYPES:
                return json_response(f"Format non supporté : {mime_type}", HttpCode.BAD_REQUEST)

            tx_id = request.form.get('tx_id')
            if not tx_id:
                return json_response('tx_id requis', HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            tx = Transactions.query.filter(
                Transactions.id == tx_id, Transactions.user_id == user_id
            ).first()
            if not tx:
                return json_response('Transaction introuvable', HttpCode.NOT_FOUND)

            doc = TransactionDocuments(
                tx_id=tx.id,
                user_id=user_id,
                original_filename=file.filename,
                mime_type=mime_type,
                file_data=file.stream.read(),
                status='confirmed',
            )
            DB.session.add(doc)
            DB.session.commit()

            return json_response({
                'id': str(doc.id),
                'original_filename': doc.original_filename,
                'mime_type': doc.mime_type,
                'uploaded_at': doc.uploaded_at.isoformat(),
            }, HttpCode.CREATED)

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, DOCUMENTS_PERM)
        def list_documents():
            # tx_id optionnel : fourni -> justificatifs d'une transaction précise (TransactionModal) ;
            # omis -> tous les justificatifs de l'utilisateur, avec un résumé de leur transaction liée
            # (vue "Mes justificatifs" de la page Factures).
            user_id = get_jwt_identity()
            tx_id = request.args.get('tx_id')
            query = TransactionDocuments.query.filter(
                TransactionDocuments.user_id == user_id,
                TransactionDocuments.status == 'confirmed',
            )
            if tx_id:
                query = query.filter(TransactionDocuments.tx_id == tx_id)
            docs = query.order_by(TransactionDocuments.uploaded_at.desc()).all()

            tx_ids = {d.tx_id for d in docs if d.tx_id}
            txs_by_id = {}
            amounts_by_tx = {}
            if tx_ids:
                txs_by_id = {t.id: t for t in Transactions.query.filter(Transactions.id.in_(tx_ids)).all()}
                splits_by_tx = {}
                for s in Splits.query.filter(Splits.tx_id.in_(tx_ids)).all():
                    splits_by_tx.setdefault(s.tx_id, []).append(float(s.quantity))
                amounts_by_tx = {t_id: abs(min(qtys)) for t_id, qtys in splits_by_tx.items()}

            result = []
            for d in docs:
                tx = txs_by_id.get(d.tx_id)
                result.append({
                    'id': str(d.id),
                    'original_filename': d.original_filename,
                    'mime_type': d.mime_type,
                    'uploaded_at': d.uploaded_at.isoformat(),
                    'transaction': {
                        'id': str(tx.id),
                        'description': tx.description,
                        'post_date': tx.post_date.isoformat() if tx.post_date else None,
                        'amount': amounts_by_tx.get(d.tx_id),
                    } if tx else None,
                })
            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/<document_id>", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, DOCUMENTS_PERM)
        def get_document(document_id):
            doc = TransactionDocuments.query.filter(
                TransactionDocuments.id == document_id,
                TransactionDocuments.user_id == get_jwt_identity(),
            ).first()
            if not doc:
                return json_response('Document introuvable', HttpCode.NOT_FOUND)
            return Response(doc.file_data, mimetype=doc.mime_type)

        @app.route(f"{ROUTE_PATH}/<document_id>", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, DOCUMENTS_PERM)
        def delete_document(document_id):
            doc = TransactionDocuments.query.filter(
                TransactionDocuments.id == document_id,
                TransactionDocuments.user_id == get_jwt_identity(),
            ).first()
            if not doc:
                return json_response('Document introuvable', HttpCode.NOT_FOUND)
            DB.session.delete(doc)
            DB.session.commit()
            return json_response('Document supprimé', HttpCode.OK)
