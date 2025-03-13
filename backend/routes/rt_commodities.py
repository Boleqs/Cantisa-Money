from flask import jsonify, request
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_SERVER_ROOT_PATH as SERVER_ROOT_PATH,
                            VAR_API_USER_ROOT_PATH as USER_ROOT_PATH)
from backend.utils.auth_token_checker import check_user_access, check_user_resource
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response

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
        ROUTE_PATH = f"{USER_ROOT_PATH}/commodities"
        @app.route(f"{ROUTE_PATH}/all", methods=['GET'])
        def get_all_commodities(user_id):
            try:
                print(request.authorization)
                commodities = DB.session.query(Commodities).filter(Commodities.user_id == user_id).all()
                if commodities:
                    commodities_list = []
                    for commodity in commodities:
                        commodities_list.append(as_dict(commodity))
                    return json_response(commodities_list, JsonResponseType.SUCCESS), HttpCode.OK
            except RoutesException as error:
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR

        @app.route(f"{ROUTE_PATH}/<uuid:id>", methods=['GET'])
        @check_user_resource(Commodities)
        def get_commodity_by_id(user_id, commodity_id):
            try:
                commodity = DB.session.query(Commodities).filter(Commodities.id == commodity_id).first()
                if commodity:
                    return json_response(as_dict(commodity), JsonResponseType.SUCCESS), HttpCode.OK
                else:
                    raise RoutesException
            except RoutesException as error:
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR
