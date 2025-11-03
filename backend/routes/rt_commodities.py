from flask import jsonify, request
from backend.config import (HttpCode,
                            JsonResponseType,
                            VAR_API_ROOT_PATH as ROOT_PATH)
from backend.utils.exceptions import RoutesException
from backend.utils.api_responses import json_response

from flask_jwt_extended import get_jwt_identity, jwt_required


def as_dict(commodity) -> dict:
    return {'fields': {'id': commodity.id,
                        'name': commodity.name,
                        'short_name': commodity.short_name,
                        'type': commodity.type,
                        'fraction': commodity.fraction,
                        'description': commodity.description},
            'infos': {'created_at': commodity.created_at}}


class CommoditiesRoutes:
    def __init__(self, app, DB, Users, Commodities):
        ROUTE_PATH = f"{ROOT_PATH}/commodities"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        def get_commodity():
            try:
                commodity = Commodities.query.filter(Commodities.id == request.args.get('commodity_id'),
                                                     Commodities.user_id == get_jwt_identity()).first()
                if bool(commodity):
                    return json_response(as_dict(commodity), JsonResponseType.SUCCESS), HttpCode.OK
                else:
                    raise RoutesException.NotFound
            except RoutesException.NotFound as error:
                return json_response(str(error), JsonResponseType.FAILURE), HttpCode.SERVER_ERROR

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        def add_commodity():
            try:
                if Commodities.query.filter(Users.id == get_jwt_identity(),
                                            Commodities.name == request.args.get("name")).first():
                    return json_response("Commodity already exists", HttpCode.FORBIDDEN)
                commodity = Commodities(user_id=get_jwt_identity(), name=request.args.get("name"),
                                        short_name=request.args.get("short_name"), type=request.args.get("type"),
                                        fraction=request.args.get("fraction"), description=request.args.get("description"))
                DB.session.add(commodity)
                DB.session.commit()
                return json_response("Commodity created", HttpCode.CREATED)
            except Exception as error:
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        def delete_commodity():
            try:
                commodity = Commodities.query.filter(Users.id == get_jwt_identity(),
                                         Commodities.id == request.args.get("id")).first()
                if bool(commodity):
                    DB.session.delete(commodity)
                else:
                    return json_response("Commodity doesn't exist", HttpCode.NOT_FOUND)
                return json_response("Commodity deleted", HttpCode.OK)
            except Exception as error:
                return json_response(str(error), HttpCode.SERVER_ERROR)