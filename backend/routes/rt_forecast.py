from decimal import Decimal

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.forecast import project_wealth

WEALTH_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']

# Presets d'horizon (mois) proposés côté frontend — validés ici pour éviter une projection
# arbitrairement longue (coût de calcul) ou négative.
VALID_HORIZONS = (12, 36, 60, 120, 240)


class ForecastWealthSchema(Schema):
    horizon_months = fields.Integer(load_default=60, validate=validate.OneOf(VALID_HORIZONS))
    growth_financial_pct = fields.Decimal(load_default=Decimal('5.0'), as_string=False)
    growth_physical_pct = fields.Decimal(load_default=Decimal('2.0'), as_string=False)
    growth_cash_pct = fields.Decimal(load_default=Decimal('3.0'), as_string=False)
    avg_monthly_net_flow = fields.Decimal(load_default=None, allow_none=True, as_string=False)
    currency = fields.String(load_default='EUR')


class ForecastRoutes:
    def __init__(self, app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                 Loans, LoanInstallments, Subscriptions, DcaPlans, Transactions, Splits, Users, FinancialGoals=None):
        ROUTE_PATH = f"{ROOT_PATH}/forecast"

        @app.route(f"{ROUTE_PATH}/wealth", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, WEALTH_PERM)
        def get_wealth_forecast():
            try:
                data = ForecastWealthSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            goals = []
            if FinancialGoals is not None:
                for g in FinancialGoals.query.filter_by(user_id=user_id).all():
                    goals.append({
                        'id': str(g.id),
                        'name': g.name,
                        'goal_type': g.goal_type,
                        'target_amount': float(g.target_amount),
                        'target_date': g.target_date.date(),
                        'end_date': g.end_date.date() if g.end_date else None,
                    })
            result = project_wealth(
                DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                Loans, LoanInstallments, Subscriptions, DcaPlans, Transactions, Splits, user_id,
                horizon_months=data['horizon_months'],
                growth_financial_pct=float(data['growth_financial_pct']),
                growth_physical_pct=float(data['growth_physical_pct']),
                growth_cash_pct=float(data['growth_cash_pct']),
                avg_monthly_net_flow_override=float(data['avg_monthly_net_flow']) if data['avg_monthly_net_flow'] is not None else None,
                target_currency=data['currency'].upper(),
                goals=goals,
            )
            return json_response(result, HttpCode.OK)
