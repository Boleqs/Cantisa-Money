from flask import jsonify, request
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH)
from backend.utils.auth_token_checker import is_user_resource, auth_required
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response

from flask_jwt_extended import get_jwt_identity, jwt_required


def as_dict(commodity) -> dict:
    return {'fields' : {'id': commodity.id,
                        'name': commodity.name,
                        'short_name': commodity.short_name,
                        'type': commodity.type,
                        'fraction': commodity.fraction,
                        'description': commodity.description},
            'infos': {'created_at': commodity.created_at}}

class CommoditiesRoutes:
    def __init__(self, app, DB, Users, Commodities):
        ROUTE_PATH = f"{ROOT_PATH}/commodities"
        @app.route(f"{ROUTE_PATH}/all", methods=['GET'])
        @jwt_required()
        def get_all_commodities():
            try:
                user_id = request.args.get('user_id')
                commodities = DB.session.query(Commodities).filter(Commodities.user_id == get_jwt_identity()).all()
                if commodities:
                    commodities_list = []
                    for commodity in commodities:
                        commodities_list.append(as_dict(commodity))
                    return json_response(commodities_list, JsonResponseType.SUCCESS), HttpCode.OK
            except Exception:
                return json_response(str(RoutesException), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR

        @app.route(f"{ROUTE_PATH}/<uuid:id>", methods=['GET'])
        @is_user_resource(Commodities)
        def get_commodity_by_id(id):
            try:
                commodity = DB.session.query(Commodities).filter(Commodities.id == id).first()
                if commodity:
                    return json_response(as_dict(commodity), JsonResponseType.SUCCESS), HttpCode.OK
                else:
                    raise RoutesException
            except RoutesException as error:
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR
