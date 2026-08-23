import io
import os
import zipfile
from datetime import datetime

from marshmallow import Schema, fields, ValidationError, validate
from flask import request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.receipt_ocr import extract_text

VAULT_PERM = VAR_PERMISSIONS_LIST['Dossier financier']['id']

ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'application/pdf'}

VALID_CATEGORIES = ('Banque', 'Immobilier', 'Assurance', 'Fiscal', 'Crédits',
                     'Retraite & épargne', 'Juridique')


def _zip_path(doc_id, original_filename):
    """Nom de fichier sûr dans l'archive — même principe que rt_backup.py::_doc_zip_path (basename
    seul, jamais de séparateur de chemin fourni par l'utilisateur, préfixé par l'id pour garantir
    l'unicité même si deux documents partagent le même nom d'origine)."""
    safe_name = os.path.basename(original_filename or 'document').strip() or 'document'
    return f"{doc_id}_{safe_name}"


def _doc_to_dict(d):
    return {
        'id': str(d.id),
        'original_filename': d.original_filename,
        'mime_type': d.mime_type,
        'file_size': d.file_size or 0,
        'category': d.category,
        'description': d.description,
        'linked_account_id': str(d.linked_account_id) if d.linked_account_id else None,
        'linked_asset_id': str(d.linked_asset_id) if d.linked_asset_id else None,
        'linked_loan_id': str(d.linked_loan_id) if d.linked_loan_id else None,
        'uploaded_at': d.uploaded_at.isoformat() if d.uploaded_at else None,
    }


class UpdateDocumentSchema(Schema):
    document_id = fields.UUID(required=True)
    category = fields.String(required=True, validate=validate.OneOf(VALID_CATEGORIES))
    description = fields.String(load_default=None, allow_none=True)
    linked_account_id = fields.UUID(load_default=None, allow_none=True)
    linked_asset_id = fields.UUID(load_default=None, allow_none=True)
    linked_loan_id = fields.UUID(load_default=None, allow_none=True)


def _check_single_link(data):
    """Au plus un des trois liens — même règle que la CheckConstraint en base
    (num_nonnulls <= 1), vérifiée ici en amont pour renvoyer une erreur 400 propre plutôt qu'une
    violation de contrainte SQL brute."""
    links = [data.get('linked_account_id'), data.get('linked_asset_id'), data.get('linked_loan_id')]
    if sum(1 for l in links if l is not None) > 1:
        return json_response(
            "Un document ne peut être lié qu'à un seul élément (compte, actif ou prêt)", HttpCode.BAD_REQUEST)
    return None


class FinancialDocumentsRoutes:
    def __init__(self, app, DB, FinancialDocuments, Accounts, Assets, Loans, Users):
        ROUTE_PATH = f"{ROOT_PATH}/financial-documents"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, VAULT_PERM)
        def list_financial_documents():
            user_id = get_jwt_identity()
            query = FinancialDocuments.query.filter(FinancialDocuments.user_id == user_id)

            category = request.args.get('category')
            if category:
                query = query.filter(FinancialDocuments.category == category)

            q = (request.args.get('q') or '').strip()
            if q:
                like = f"%{q}%"
                query = query.filter(or_(
                    FinancialDocuments.original_filename.ilike(like),
                    FinancialDocuments.description.ilike(like),
                    FinancialDocuments.extracted_text.ilike(like),
                ))

            docs = query.order_by(FinancialDocuments.uploaded_at.desc()).all()
            return json_response([_doc_to_dict(d) for d in docs], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, VAULT_PERM)
        def add_financial_document():
            file = request.files.get('file')
            if not file:
                return json_response('Aucun fichier fourni', HttpCode.BAD_REQUEST)

            mime_type = file.mimetype
            if mime_type not in ALLOWED_MIME_TYPES:
                return json_response(f"Format non supporté : {mime_type}", HttpCode.BAD_REQUEST)

            category = request.form.get('category')
            if category not in VALID_CATEGORIES:
                return json_response('Catégorie invalide', HttpCode.BAD_REQUEST)

            data = {
                'linked_account_id': request.form.get('linked_account_id') or None,
                'linked_asset_id': request.form.get('linked_asset_id') or None,
                'linked_loan_id': request.form.get('linked_loan_id') or None,
            }
            error = _check_single_link(data)
            if error:
                return error

            user_id = get_jwt_identity()
            if data['linked_account_id']:
                account = Accounts.query.filter(
                    Accounts.id == data['linked_account_id'], Accounts.user_id == user_id).first()
                if not account:
                    return json_response('Compte introuvable', HttpCode.NOT_FOUND)
            if data['linked_asset_id']:
                asset = Assets.query.filter(
                    Assets.id == data['linked_asset_id'], Assets.user_id == user_id).first()
                if not asset:
                    return json_response('Actif introuvable', HttpCode.NOT_FOUND)
            if data['linked_loan_id']:
                loan = Loans.query.filter(
                    Loans.id == data['linked_loan_id'], Loans.user_id == user_id).first()
                if not loan:
                    return json_response('Prêt introuvable', HttpCode.NOT_FOUND)

            file_bytes = file.stream.read()
            # L'OCR n'est qu'un bonus pour la recherche dans le contenu — son échec ne doit jamais
            # empêcher l'enregistrement du document lui-même (contrairement à rt_documents.py::parse,
            # où l'OCR est indispensable au flux et fait donc échouer la requête).
            try:
                extracted_text = extract_text(file_bytes, mime_type)
            except Exception:
                extracted_text = None

            doc = FinancialDocuments(
                user_id=user_id,
                original_filename=file.filename,
                mime_type=mime_type,
                file_data=file_bytes,
                file_size=len(file_bytes),
                category=category,
                description=request.form.get('description') or None,
                extracted_text=extracted_text,
                linked_account_id=data['linked_account_id'],
                linked_asset_id=data['linked_asset_id'],
                linked_loan_id=data['linked_loan_id'],
            )
            DB.session.add(doc)
            DB.session.commit()
            return json_response(_doc_to_dict(doc), HttpCode.CREATED)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, VAULT_PERM)
        def update_financial_document():
            try:
                data = UpdateDocumentSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            error = _check_single_link(data)
            if error:
                return error

            user_id = get_jwt_identity()
            doc = FinancialDocuments.query.filter(
                FinancialDocuments.id == data['document_id'], FinancialDocuments.user_id == user_id).first()
            if not doc:
                return json_response('Document introuvable', HttpCode.NOT_FOUND)

            if data.get('linked_account_id'):
                account = Accounts.query.filter(
                    Accounts.id == data['linked_account_id'], Accounts.user_id == user_id).first()
                if not account:
                    return json_response('Compte introuvable', HttpCode.NOT_FOUND)
            if data.get('linked_asset_id'):
                asset = Assets.query.filter(
                    Assets.id == data['linked_asset_id'], Assets.user_id == user_id).first()
                if not asset:
                    return json_response('Actif introuvable', HttpCode.NOT_FOUND)
            if data.get('linked_loan_id'):
                loan = Loans.query.filter(
                    Loans.id == data['linked_loan_id'], Loans.user_id == user_id).first()
                if not loan:
                    return json_response('Prêt introuvable', HttpCode.NOT_FOUND)

            try:
                doc.category = data['category']
                doc.description = data.get('description')
                doc.linked_account_id = data.get('linked_account_id')
                doc.linked_asset_id = data.get('linked_asset_id')
                doc.linked_loan_id = data.get('linked_loan_id')
                DB.session.commit()
                return json_response(_doc_to_dict(doc), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/export", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, VAULT_PERM)
        def export_financial_documents():
            user_id = get_jwt_identity()
            query = FinancialDocuments.query.filter(FinancialDocuments.user_id == user_id)
            category = request.args.get('category')
            if category:
                query = query.filter(FinancialDocuments.category == category)
            docs = query.order_by(FinancialDocuments.uploaded_at.desc()).all()

            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for d in docs:
                    zf.writestr(_zip_path(d.id, d.original_filename), d.file_data)
            buffer.seek(0)

            suffix = f"-{category}" if category else ''
            filename = f"dossier-financier{suffix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
            return Response(
                buffer.getvalue(),
                mimetype='application/zip',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'})

        @app.route(f"{ROUTE_PATH}/<document_id>", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, VAULT_PERM)
        def get_financial_document(document_id):
            doc = FinancialDocuments.query.filter(
                FinancialDocuments.id == document_id, FinancialDocuments.user_id == get_jwt_identity()).first()
            if not doc:
                return json_response('Document introuvable', HttpCode.NOT_FOUND)
            return Response(doc.file_data, mimetype=doc.mime_type)

        @app.route(f"{ROUTE_PATH}/<document_id>", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, VAULT_PERM)
        def delete_financial_document(document_id):
            doc = FinancialDocuments.query.filter(
                FinancialDocuments.id == document_id, FinancialDocuments.user_id == get_jwt_identity()).first()
            if not doc:
                return json_response('Document introuvable', HttpCode.NOT_FOUND)
            DB.session.delete(doc)
            DB.session.commit()
            return json_response('Document supprimé', HttpCode.OK)
