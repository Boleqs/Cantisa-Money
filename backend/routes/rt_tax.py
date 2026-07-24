from datetime import date

from flask import request
from marshmallow import Schema, fields, ValidationError, validate, EXCLUDE
from sqlalchemy import func
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission

TAX_PERM = VAR_PERMISSIONS_LIST['Fiscalité']['id']
WEALTH_TYPES = ('Current', 'Assets', 'Equity')
TAX_TREATMENTS = ('taxable_income', 'deductible', 'real_estate_income', 'real_estate_expense')

# Barème par défaut proposé au premier accès — non vérifié (voir is_verified sur TaxRegime), à
# ajuster par l'utilisateur. Le droit fiscal change chaque année, ces chiffres ne sont pas une
# vérité absolue codée en dur, juste un point de départ.
DEFAULT_FR_REGIME_CONFIG = {
    'income_tax': {
        'brackets': [
            {'upper_bound': 11497, 'rate': 0.0},
            {'upper_bound': 29315, 'rate': 0.11},
            {'upper_bound': 83823, 'rate': 0.30},
            {'upper_bound': 180294, 'rate': 0.41},
            {'upper_bound': None, 'rate': 0.45},
        ],
        'decote': {'enabled': True, 'threshold_single': 1929.0, 'threshold_couple': 3191.0, 'rate': 0.4525},
        'quotient_familial': {'half_part_cap': 1791.0, 'first_two_half_parts_cap': 4224.0},
    },
    'capital_gains': {},
}

# Plus-values réalisées : PFU (flat tax) uniquement en Phase 2, pas d'option barème progressif
# (voir décision 5 du plan Phase 2) — le champ 'mode' existe pour ne pas casser la compatibilité
# le jour où l'option sera ajoutée.
DEFAULT_CAPITAL_GAINS_CONFIG = {
    'mode': 'pfu', 'pfu_income_rate': 0.128, 'pfu_social_rate': 0.172, 'pea_exempt_income_after_years': 5,
}


# ── Schémas de validation du régime ──────────────────────────────────────────────

class BracketSchema(Schema):
    upper_bound = fields.Float(allow_none=True)
    rate = fields.Float(required=True, validate=validate.Range(min=0, max=1))


class DecoteSchema(Schema):
    enabled = fields.Boolean(load_default=True)
    threshold_single = fields.Float(required=True, validate=validate.Range(min=0))
    threshold_couple = fields.Float(required=True, validate=validate.Range(min=0))
    rate = fields.Float(required=True, validate=validate.Range(min=0, max=1))


class QuotientFamilialSchema(Schema):
    half_part_cap = fields.Float(required=True, validate=validate.Range(min=0))
    first_two_half_parts_cap = fields.Float(required=True, validate=validate.Range(min=0))


class IncomeTaxConfigSchema(Schema):
    brackets = fields.List(fields.Nested(BracketSchema), required=True, validate=validate.Length(min=1))
    decote = fields.Nested(DecoteSchema, required=True)
    quotient_familial = fields.Nested(QuotientFamilialSchema, required=True)


class CapitalGainsConfigSchema(Schema):
    mode = fields.String(load_default='pfu', validate=validate.OneOf(['pfu']))
    pfu_income_rate = fields.Float(load_default=0.128, validate=validate.Range(min=0, max=1))
    pfu_social_rate = fields.Float(load_default=0.172, validate=validate.Range(min=0, max=1))
    pea_exempt_income_after_years = fields.Float(load_default=5, validate=validate.Range(min=0))


class TaxRegimeConfigSchema(Schema):
    class Meta:
        # Tolère d'éventuelles clés futures sans les rejeter.
        unknown = EXCLUDE

    income_tax = fields.Nested(IncomeTaxConfigSchema, required=True)
    capital_gains = fields.Nested(CapitalGainsConfigSchema, load_default=dict)


def _validate_brackets(brackets):
    if brackets[-1]['upper_bound'] is not None:
        raise ValueError("la dernière tranche doit avoir upper_bound = null (infini)")
    for b in brackets[:-1]:
        if b['upper_bound'] is None:
            raise ValueError("seule la dernière tranche peut avoir upper_bound = null")
    bounds = [b['upper_bound'] for b in brackets[:-1]]
    if bounds != sorted(bounds) or len(set(bounds)) != len(bounds):
        raise ValueError("les tranches doivent être triées par upper_bound strictement croissant")


def _validate_regime_config(config):
    data = TaxRegimeConfigSchema().load(config)
    _validate_brackets(data['income_tax']['brackets'])
    return data


# ── Schémas des routes ────────────────────────────────────────────────────────

class AddRegimeSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    country_code = fields.String(load_default='FR', validate=validate.Length(min=2, max=2))
    tax_year = fields.Integer(required=True)
    config = fields.Dict(required=True)


class UpdateRegimeSchema(Schema):
    regime_id = fields.UUID(required=True)
    name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    country_code = fields.String(load_default='FR', validate=validate.Length(min=2, max=2))
    tax_year = fields.Integer(required=True)
    config = fields.Dict(required=True)
    is_active = fields.Boolean(load_default=False)


class HouseholdIncomeSchema(Schema):
    label = fields.String(required=True, validate=validate.Length(min=1, max=200))
    amount = fields.Float(required=True)
    income_type = fields.String(load_default='other', validate=validate.Length(max=32))


class UpdateHouseholdSchema(Schema):
    tax_year = fields.Integer(required=True)
    adults = fields.Integer(required=True, validate=validate.Range(min=1, max=2))
    dependents = fields.Integer(load_default=0, validate=validate.Range(min=0))
    dependents_disabled = fields.Integer(load_default=0, validate=validate.Range(min=0))
    parent_isole = fields.Boolean(load_default=False)
    notes = fields.String(load_default=None, allow_none=True)
    incomes = fields.List(fields.Nested(HouseholdIncomeSchema), load_default=list)


# ── Moteur de calcul ──────────────────────────────────────────────────────────

def _compute_parts(profile):
    """Retourne (parts, parts_référence) — parts_référence sert au plafonnement du quotient
    familial (bénéfice fiscal des parts liées aux personnes à charge)."""
    base = 2.0 if profile.adults == 2 else 1.0
    dep = profile.dependents
    dep_parts = min(dep, 2) * 0.5 + max(0, dep - 2) * 1.0
    isole_bonus = 0.5 if (profile.parent_isole and dep >= 1) else 0.0
    disabled_bonus = 0.5 * profile.dependents_disabled
    return base + dep_parts + isole_bonus + disabled_bonus, base


def _apply_bracket_schedule(quotient, brackets):
    """Impôt par part pour un barème donné + taux marginal atteint."""
    tax, lower, marginal = 0.0, 0.0, 0.0
    for b in brackets:
        upper, rate = b['upper_bound'], b['rate']
        ceiling = upper if upper is not None else quotient
        if quotient > lower:
            taxed = min(quotient, ceiling) - lower
            if taxed > 0:
                tax += taxed * rate
                marginal = rate
        if upper is not None and quotient <= upper:
            break
        lower = upper if upper is not None else lower
    return tax, marginal


def _compute_ir(taxable_income, parts, reference_parts, profile, config):
    brackets = config['income_tax']['brackets']

    quotient_full = taxable_income / parts if parts > 0 else taxable_income
    tax_per_part_full, marginal_rate = _apply_bracket_schedule(quotient_full, brackets)
    gross_tax_full = tax_per_part_full * parts

    quotient_ref = taxable_income / reference_parts if reference_parts > 0 else taxable_income
    tax_per_part_ref, _ = _apply_bracket_schedule(quotient_ref, brackets)
    gross_tax_ref = tax_per_part_ref * reference_parts

    tax_benefit = max(0.0, gross_tax_ref - gross_tax_full)
    qf = config['income_tax']['quotient_familial']
    extra_half_parts = round((parts - reference_parts) * 2)
    if profile.parent_isole and extra_half_parts > 0:
        capped_benefit = qf['first_two_half_parts_cap'] + max(0, extra_half_parts - 1) * qf['half_part_cap']
    else:
        capped_benefit = extra_half_parts * qf['half_part_cap']

    cap_applied = tax_benefit > capped_benefit
    gross_tax = max(0.0, (gross_tax_ref - capped_benefit) if cap_applied else gross_tax_full)

    decote_cfg = config['income_tax']['decote']
    decote_amount = 0.0
    if decote_cfg.get('enabled'):
        threshold = decote_cfg['threshold_couple'] if profile.adults == 2 else decote_cfg['threshold_single']
        if 0 < gross_tax < threshold:
            decote_amount = min(gross_tax, max(0.0, threshold - decote_cfg['rate'] * gross_tax))

    return {
        'quotient': round(quotient_full, 2),
        'marginal_rate': marginal_rate,
        'gross_tax_before_qf_cap': round(gross_tax_full, 2),
        'gross_tax_reference_parts': round(gross_tax_ref, 2),
        'quotient_familial_cap_applied': cap_applied,
        'gross_tax': round(gross_tax, 2),
        'decote_amount': round(decote_amount, 2),
        'net_tax_estimated': round(max(0.0, gross_tax - decote_amount), 2),
    }


def _regime_to_dict(r):
    return {
        'id': str(r.id), 'name': r.name, 'country_code': r.country_code, 'tax_year': r.tax_year,
        'config': r.config, 'is_active': r.is_active, 'is_verified': r.is_verified,
        'created_at': r.created_at.isoformat() if r.created_at else None,
        'updated_at': r.updated_at.isoformat() if r.updated_at else None,
    }


class TaxRoutes:
    def __init__(self, app, DB, Users, TaxRegime, TaxHouseholdProfile, TaxHouseholdIncome, Categories,
                 Transactions, Splits, Accounts, Commodities, FxRates, UserSettings,
                 AssetDisposal, AssetPossession, Assets):
        ROUTE_PATH = f"{ROOT_PATH}/tax"

        def _target_currency(user_id):
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            return settings.currency if settings else 'EUR'

        _rate_cache = {}

        def _rate_to(code, target_currency):
            if code == target_currency:
                return 1.0
            key = (code, target_currency)
            if key not in _rate_cache:
                _rate_cache[key] = get_fx_rate(code, target_currency, FxRates) or 0.0
            return _rate_cache[key]

        def _ensure_default_regime(user_id):
            existing = TaxRegime.query.filter_by(user_id=user_id).first()
            if existing:
                return TaxRegime.query.filter_by(user_id=user_id, is_active=True).first() or existing
            regime = TaxRegime(
                user_id=user_id,
                name=f"France {date.today().year}",
                country_code='FR',
                tax_year=date.today().year,
                config=DEFAULT_FR_REGIME_CONFIG,
                is_active=True,
                is_verified=False,
            )
            DB.session.add(regime)
            DB.session.commit()
            return regime

        def _sum_by_tax_treatment(user_id, year, target_currency, treatments, sign):
            rows = DB.session.query(Commodities.short_name, func.sum(Splits.quantity)) \
                .join(Transactions, Splits.tx_id == Transactions.id) \
                .join(Categories, Transactions.category_id == Categories.id) \
                .join(Accounts, Splits.account_id == Accounts.id) \
                .join(Commodities, Accounts.currency_id == Commodities.id) \
                .filter(
                    Transactions.user_id == user_id,
                    Categories.tax_treatment.in_(treatments),
                    Transactions.post_date >= date(year, 1, 1),
                    Transactions.post_date <= date(year, 12, 31),
                    Splits.quantity * sign > 0,
                    Accounts.account_type.in_(WEALTH_TYPES),
                    Accounts.is_virtual == False,
                    Accounts.is_hidden == False,
                ).group_by(Commodities.short_name).all()
            return abs(sum(float(t) * _rate_to(code, target_currency) for code, t in rows))

        def _compute_capital_gains(user_id, year, target_currency, regime_config):
            """PFU (flat tax) sur les cessions réalisées dans l'année — voir décision 5 du plan
            Phase 2 : pas d'option barème progressif. Fusion défensive avec les valeurs par défaut
            car simulate_ir lit regime.config directement (les régimes Phase 1 ont
            capital_gains == {})."""
            cg = {**DEFAULT_CAPITAL_GAINS_CONFIG, **(regime_config.get('capital_gains') or {})}

            rows = DB.session.query(AssetDisposal, AssetPossession, Accounts, Commodities) \
                .join(AssetPossession, AssetDisposal.possession_id == AssetPossession.id) \
                .join(Accounts, AssetPossession.account_id == Accounts.id) \
                .join(Assets, AssetPossession.asset_id == Assets.id) \
                .join(Commodities, Assets.commodity_id == Commodities.id) \
                .filter(
                    AssetDisposal.user_id == user_id,
                    AssetDisposal.sale_date >= date(year, 1, 1),
                    AssetDisposal.sale_date <= date(year, 12, 31),
                ).all()

            total_realized_gain, exempt_gain_pea, disposal_count, unknown_cost_basis_count = 0.0, 0.0, 0, 0
            pea_years = cg['pea_exempt_income_after_years']
            for disposal, possession, account, commodity in rows:
                disposal_count += 1
                if disposal.realized_gain is None:
                    unknown_cost_basis_count += 1
                    continue
                gain = float(disposal.realized_gain) * _rate_to(commodity.short_name, target_currency)
                total_realized_gain += gain

                is_pea = (
                    account.account_type == 'Equity' and getattr(account, 'account_subtype', None) == 'fr_PEA'
                    and possession.purchase_date is not None
                    and (disposal.sale_date - possession.purchase_date).days / 365.25 >= pea_years
                )
                if is_pea and gain > 0:
                    exempt_gain_pea += gain

            taxable_gain = max(0.0, total_realized_gain - exempt_gain_pea)
            pfu_income_tax_due = taxable_gain * cg['pfu_income_rate']
            # Les prélèvements sociaux s'appliquent à la totalité du gain, y compris la part
            # exonérée d'impôt via le PEA — seule la composante "impôt" est exonérée.
            pfu_social_tax_due = max(0.0, total_realized_gain) * cg['pfu_social_rate']

            return {
                'mode': cg['mode'],
                'total_realized_gain': round(total_realized_gain, 2),
                'exempt_gain_pea': round(exempt_gain_pea, 2),
                'taxable_gain': round(taxable_gain, 2),
                'pfu_income_rate': cg['pfu_income_rate'],
                'pfu_social_rate': cg['pfu_social_rate'],
                'pfu_income_tax_due': round(pfu_income_tax_due, 2),
                'pfu_social_tax_due': round(pfu_social_tax_due, 2),
                'pfu_total_due': round(pfu_income_tax_due + pfu_social_tax_due, 2),
                'disposal_count': disposal_count,
                'unknown_cost_basis_count': unknown_cost_basis_count,
            }

        # ── Régimes fiscaux ────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/regimes", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, TAX_PERM)
        def get_regimes():
            user_id = get_jwt_identity()
            _ensure_default_regime(user_id)
            regimes = TaxRegime.query.filter_by(user_id=user_id).order_by(TaxRegime.name).all()
            return json_response([_regime_to_dict(r) for r in regimes], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/regimes", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, TAX_PERM)
        def add_regime():
            try:
                data = AddRegimeSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            if TaxRegime.query.filter_by(user_id=user_id, name=data['name']).first():
                return json_response('Un régime porte déjà ce nom', HttpCode.CONFLICT)
            try:
                _validate_regime_config(data['config'])
            except (ValidationError, ValueError) as e:
                return json_response(str(e), HttpCode.BAD_REQUEST)
            try:
                regime = TaxRegime(
                    user_id=user_id, name=data['name'], country_code=data['country_code'],
                    tax_year=data['tax_year'], config=data['config'], is_active=False, is_verified=True,
                )
                DB.session.add(regime)
                DB.session.commit()
                return json_response(_regime_to_dict(regime), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/regimes", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, TAX_PERM)
        def update_regime():
            try:
                data = UpdateRegimeSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            regime = TaxRegime.query.filter_by(id=data['regime_id'], user_id=user_id).first()
            if not regime:
                return json_response('Régime introuvable', HttpCode.NOT_FOUND)
            try:
                _validate_regime_config(data['config'])
            except (ValidationError, ValueError) as e:
                return json_response(str(e), HttpCode.BAD_REQUEST)
            try:
                regime.name = data['name']
                regime.country_code = data['country_code']
                regime.tax_year = data['tax_year']
                regime.config = data['config']
                regime.is_verified = True
                if data['is_active']:
                    TaxRegime.query.filter(
                        TaxRegime.user_id == user_id, TaxRegime.id != regime.id
                    ).update({'is_active': False})
                    regime.is_active = True
                elif regime.is_active and not data['is_active']:
                    regime.is_active = False
                DB.session.commit()
                return json_response(_regime_to_dict(regime), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/regimes", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, TAX_PERM)
        def delete_regime():
            regime_id = request.args.get('regime_id')
            if not regime_id:
                return json_response('regime_id requis', HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            regime = TaxRegime.query.filter_by(id=regime_id, user_id=user_id).first()
            if not regime:
                return json_response('Régime introuvable', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(regime)
                DB.session.commit()
                return json_response('Régime supprimé', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        # ── Foyer fiscal ───────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/household", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, TAX_PERM)
        def get_household():
            user_id = get_jwt_identity()
            year = int(request.args.get('year', date.today().year))
            profile = TaxHouseholdProfile.query.filter_by(user_id=user_id, tax_year=year).first()
            if not profile:
                return json_response({
                    'tax_year': year, 'adults': 1, 'dependents': 0, 'dependents_disabled': 0,
                    'parent_isole': False, 'notes': None, 'incomes': [], 'exists': False,
                }, HttpCode.OK)
            incomes = TaxHouseholdIncome.query.filter_by(household_profile_id=profile.id).all()
            return json_response({
                'tax_year': profile.tax_year, 'adults': profile.adults, 'dependents': profile.dependents,
                'dependents_disabled': profile.dependents_disabled, 'parent_isole': profile.parent_isole,
                'notes': profile.notes,
                'incomes': [{'id': str(i.id), 'label': i.label, 'amount': float(i.amount),
                            'income_type': i.income_type} for i in incomes],
                'exists': True,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/household", methods=['PUT'])
        @jwt_required()
        @restricted_by_permission(Users, TAX_PERM)
        def update_household():
            try:
                data = UpdateHouseholdSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            try:
                profile = TaxHouseholdProfile.query.filter_by(user_id=user_id, tax_year=data['tax_year']).first()
                if not profile:
                    profile = TaxHouseholdProfile(user_id=user_id, tax_year=data['tax_year'])
                    DB.session.add(profile)
                    DB.session.flush()
                profile.adults = data['adults']
                profile.dependents = data['dependents']
                profile.dependents_disabled = data['dependents_disabled']
                profile.parent_isole = data['parent_isole']
                profile.notes = data.get('notes')

                TaxHouseholdIncome.query.filter_by(household_profile_id=profile.id).delete()
                for inc in data['incomes']:
                    DB.session.add(TaxHouseholdIncome(
                        household_profile_id=profile.id, label=inc['label'],
                        amount=inc['amount'], income_type=inc['income_type'],
                    ))
                DB.session.commit()
                return json_response({'tax_year': profile.tax_year}, HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        # ── Simulation ─────────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/simulate", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, TAX_PERM)
        def simulate_ir():
            user_id = get_jwt_identity()
            year = int(request.args.get('year', date.today().year))
            target_currency = _target_currency(user_id)

            taxable_tracked = _sum_by_tax_treatment(user_id, year, target_currency, ('taxable_income',), 1)
            deductible_tracked = _sum_by_tax_treatment(user_id, year, target_currency, ('deductible',), -1)
            re_income = _sum_by_tax_treatment(user_id, year, target_currency, ('real_estate_income',), 1)
            re_expense = _sum_by_tax_treatment(user_id, year, target_currency, ('real_estate_expense',), -1)
            # Pas de déficit foncier imputable sur le revenu global en Phase 1 — un revenu foncier
            # net négatif est simplement ramené à 0 plutôt que de réduire le revenu imposable total.
            real_estate_net = max(0.0, re_income - re_expense)

            profile = TaxHouseholdProfile.query.filter_by(user_id=user_id, tax_year=year).first()
            profile_missing = profile is None
            if profile_missing:
                profile = TaxHouseholdProfile(adults=1, dependents=0, dependents_disabled=0, parent_isole=False)
                extra_income = 0.0
            else:
                extra_income = sum(
                    float(i.amount) for i in
                    TaxHouseholdIncome.query.filter_by(household_profile_id=profile.id).all()
                )

            taxable_income_total = taxable_tracked - deductible_tracked + real_estate_net + extra_income
            parts, reference_parts = _compute_parts(profile)

            regime = TaxRegime.query.filter_by(user_id=user_id, is_active=True).first()
            if not regime:
                regime = _ensure_default_regime(user_id)
            year_mismatch = regime.tax_year != year

            computation = _compute_ir(taxable_income_total, parts, reference_parts, profile, regime.config)
            capital_gains = _compute_capital_gains(user_id, year, target_currency, regime.config)

            return json_response({
                'tax_year': year,
                'currency': target_currency,
                'regime': {
                    'id': str(regime.id), 'name': regime.name, 'tax_year': regime.tax_year,
                    'is_verified': regime.is_verified, 'year_mismatch': year_mismatch,
                },
                'household': {
                    'parts': parts, 'reference_parts': reference_parts,
                    'adults': profile.adults, 'dependents': profile.dependents,
                    'profile_missing': profile_missing,
                },
                'income': {
                    'taxable_income_tracked': round(taxable_tracked, 2),
                    'deductible_tracked': round(deductible_tracked, 2),
                    'real_estate_net': round(real_estate_net, 2),
                    'extra_household_income': round(extra_income, 2),
                    'taxable_income_total': round(taxable_income_total, 2),
                },
                'computation': computation,
                'capital_gains': capital_gains,
            }, HttpCode.OK)
