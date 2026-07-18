from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

SETTINGS_PERM = VAR_PERMISSIONS_LIST['Réglages personnels']['id']
VALID_DATE_FORMATS = ('fr-FR', 'en-GB', 'en-US', 'iso')

DEFAULT_SETTINGS = {
    'currency': 'EUR',
    'date_format': 'fr-FR',
    'market_score_weights': None,
    'market_score_thresholds': None,
}


class UpdateSettingsSchema(Schema):
    # Pas de validate.OneOf figé ici : les devises valides dépendent des devises que l'utilisateur
    # a lui-même créées (table commodities), vérifié dynamiquement dans update_settings().
    currency = fields.String(load_default='EUR')
    date_format = fields.String(load_default='fr-FR', validate=validate.OneOf(VALID_DATE_FORMATS))
    market_score_weights = fields.Dict(load_default=None, allow_none=True)
    market_score_thresholds = fields.Dict(load_default=None, allow_none=True)


def _settings_to_dict(s):
    return {
        'currency': s.currency,
        'date_format': s.date_format,
        'market_score_weights': s.market_score_weights,
        'market_score_thresholds': s.market_score_thresholds,
    }


class SettingsRoutes:
    def __init__(self, app, DB, UserSettings, Users, Commodities):
        ROUTE_PATH = f"{ROOT_PATH}/settings"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, SETTINGS_PERM)
        def get_settings():
            s = UserSettings.query.filter_by(user_id=get_jwt_identity()).first()
            if not s:
                return json_response(DEFAULT_SETTINGS, HttpCode.OK)
            return json_response(_settings_to_dict(s), HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['PUT'])
        @jwt_required()
        @restricted_by_permission(Users, SETTINGS_PERM)
        def update_settings():
            try:
                data = UpdateSettingsSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            if not Commodities.query.filter_by(
                    user_id=user_id, type='Currency', short_name=data['currency']).first():
                return json_response(
                    "Devise inconnue — ajoutez-la d'abord dans Paramétrage > Devises",
                    HttpCode.BAD_REQUEST)
            try:
                s = UserSettings.query.filter_by(user_id=user_id).first()
                if not s:
                    s = UserSettings(user_id=user_id)
                    DB.session.add(s)
                s.currency = data['currency']
                s.date_format = data['date_format']
                s.market_score_weights = data['market_score_weights']
                s.market_score_thresholds = data['market_score_thresholds']
                DB.session.commit()
                return json_response(_settings_to_dict(s), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
