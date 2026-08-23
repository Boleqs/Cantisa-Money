from datetime import datetime

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.receipt_ocr import normalize_merchant_key, TEMPLATE_ZONE_LABELS

# Même groupe de permission que le reste du flux OCR/justificatifs (rt_documents.py) — les
# gabarits sont une configuration de ce même flux, pas une entité distincte.
RECEIPT_TEMPLATES_PERM = VAR_PERMISSIONS_LIST['Comptabilité']['id']


class ZoneSchema(Schema):
    label = fields.String(required=True, validate=validate.OneOf(TEMPLATE_ZONE_LABELS))
    top = fields.Float(required=True, validate=validate.Range(min=0, max=100))
    left = fields.Float(required=True, validate=validate.Range(min=0, max=100))
    width = fields.Float(required=True, validate=validate.Range(min=0.5, max=100))
    height = fields.Float(required=True, validate=validate.Range(min=0.5, max=100))


class AddReceiptTemplateSchema(Schema):
    merchant_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    zones = fields.List(fields.Nested(ZoneSchema), required=True, validate=validate.Length(min=1))


class UpdateReceiptTemplateSchema(Schema):
    template_id = fields.UUID(required=True)
    merchant_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    zones = fields.List(fields.Nested(ZoneSchema), required=True, validate=validate.Length(min=1))


class DeleteReceiptTemplateSchema(Schema):
    template_id = fields.UUID(required=True)


def _template_to_dict(t):
    return {
        'id': str(t.id),
        'merchant_name': t.merchant_name,
        'zones': t.zones,
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'updated_at': t.updated_at.isoformat() if t.updated_at else None,
    }


class ReceiptTemplatesRoutes:
    def __init__(self, app, DB, ReceiptTemplates, Users):
        ROUTE_PATH = f"{ROOT_PATH}/receipt-templates"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, RECEIPT_TEMPLATES_PERM)
        def list_receipt_templates():
            user_id = get_jwt_identity()
            templates = (ReceiptTemplates.query.filter_by(user_id=user_id)
                         .order_by(ReceiptTemplates.merchant_name).all())
            return json_response([_template_to_dict(t) for t in templates], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, RECEIPT_TEMPLATES_PERM)
        def add_receipt_template():
            try:
                data = AddReceiptTemplateSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            merchant_key = normalize_merchant_key(data['merchant_name'])
            if not merchant_key:
                return json_response('Nom de marchand invalide', HttpCode.BAD_REQUEST)

            try:
                # Un seul gabarit actif par marchand : réenregistrer sur le même marchand met à
                # jour l'existant plutôt que d'échouer sur la contrainte d'unicité — plus simple
                # côté frontend, qui n'a pas besoin de savoir si un gabarit existe déjà avant de
                # sauvegarder.
                existing = ReceiptTemplates.query.filter_by(user_id=user_id, merchant_key=merchant_key).first()
                if existing:
                    existing.merchant_name = data['merchant_name']
                    existing.zones = data['zones']
                    existing.updated_at = datetime.now()
                    DB.session.commit()
                    return json_response(_template_to_dict(existing), HttpCode.OK)

                t = ReceiptTemplates(
                    user_id=user_id,
                    merchant_name=data['merchant_name'],
                    merchant_key=merchant_key,
                    zones=data['zones'],
                )
                DB.session.add(t)
                DB.session.commit()
                return json_response(_template_to_dict(t), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, RECEIPT_TEMPLATES_PERM)
        def update_receipt_template():
            try:
                data = UpdateReceiptTemplateSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            t = ReceiptTemplates.query.filter(
                ReceiptTemplates.id == data['template_id'], ReceiptTemplates.user_id == user_id
            ).first()
            if not t:
                return json_response('Gabarit introuvable', HttpCode.NOT_FOUND)

            merchant_key = normalize_merchant_key(data['merchant_name'])
            if not merchant_key:
                return json_response('Nom de marchand invalide', HttpCode.BAD_REQUEST)

            conflict = ReceiptTemplates.query.filter(
                ReceiptTemplates.user_id == user_id, ReceiptTemplates.merchant_key == merchant_key,
                ReceiptTemplates.id != t.id,
            ).first()
            if conflict:
                return json_response(f'Un gabarit existe déjà pour « {conflict.merchant_name} »', HttpCode.CONFLICT)

            try:
                t.merchant_name = data['merchant_name']
                t.merchant_key = merchant_key
                t.zones = data['zones']
                t.updated_at = datetime.now()
                DB.session.commit()
                return json_response(_template_to_dict(t), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, RECEIPT_TEMPLATES_PERM)
        def delete_receipt_template():
            try:
                data = DeleteReceiptTemplateSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            t = ReceiptTemplates.query.filter(
                ReceiptTemplates.id == data['template_id'], ReceiptTemplates.user_id == user_id
            ).first()
            if not t:
                return json_response('Gabarit introuvable', HttpCode.NOT_FOUND)

            DB.session.delete(t)
            DB.session.commit()
            return json_response('Gabarit supprimé', HttpCode.OK)
