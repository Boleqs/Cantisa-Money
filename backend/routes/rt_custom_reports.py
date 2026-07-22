import uuid as uuid_lib
from datetime import date, timedelta

from flask import request
from marshmallow import Schema, fields, ValidationError, EXCLUDE
from sqlalchemy import func
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission

REPORTS_PERM = VAR_PERMISSIONS_LIST['Pilotage']['id']
WEALTH_TYPES = ('Current', 'Assets', 'Equity')
# Volontairement inchangé (n'inclut PAS 'Liability') : c'est le filtre par défaut appliqué quand
# l'utilisateur n'a pas explicitement filtré sur account_type, pour éviter de compter deux fois un
# même mouvement via les contreparties Income/Expense. Y ajouter Liability injecterait par défaut
# les mouvements de capital d'un crédit (déblocage, remboursements) dans des agrégations pensées
# pour des flux réels (revenus/dépenses) — l'utilisateur peut toujours cibler explicitement les
# comptes Liability via un filtre account_type (voir ACCOUNT_TYPES ci-dessous).
ACCOUNT_TYPES = ('Income', 'Expense', 'Equity', 'Assets', 'Current', 'Liability')

GROUP_BY_OPTIONS = {'category', 'tag', 'account', 'day', 'week', 'month', 'year', 'none'}
METRIC_OPTIONS = {'sum', 'count', 'avg'}
DATE_GROUPS = {'day': '%Y-%m-%d', 'week': '%Y-%m-%d', 'month': '%Y-%m', 'year': '%Y'}


# ── Casts ────────────────────────────────────────────────────────────────────

def _cast_uuid(v):
    return uuid_lib.UUID(str(v))


def _cast_float(v):
    return float(v)


def _cast_str(v):
    return str(v)


def _cast_bool(v):
    return bool(v)


def _cast_account_type(v):
    v = str(v)
    if v not in ACCOUNT_TYPES:
        raise ValueError(f"type de compte invalide : {v}")
    return v


# Liste blanche champ -> opérateurs autorisés + cast. Aucune valeur utilisateur n'atteint jamais
# le SQL sans passer par cast() (uuid/float/bool/enum stricts) — pas de SQL construit par
# concaténation de chaînes.
FIELD_SPECS = {
    'account_id':   {'ops': {'eq', 'ne', 'in'}, 'cast': _cast_uuid},
    'category_id':  {'ops': {'eq', 'ne', 'in', 'is_null'}, 'cast': _cast_uuid},
    'tag_id':       {'ops': {'eq', 'in'}, 'cast': _cast_uuid},
    'account_type': {'ops': {'eq', 'ne', 'in'}, 'cast': _cast_account_type},
    # Filtre sur le montant natif du split (avant conversion de devise) — filtrer un montant
    # converti nécessiterait une jointure de taux par ligne, disproportionné pour ce constructeur.
    'amount':       {'ops': {'eq', 'ne', 'gt', 'gte', 'lt', 'lte'}, 'cast': _cast_float},
    'description':  {'ops': {'contains'}, 'cast': _cast_str},
    'is_cleared':   {'ops': {'eq'}, 'cast': _cast_bool},
}


def _apply_operator(column, operator, value):
    if operator == 'is_null':
        return column.is_(None) if bool(value) else column.isnot(None)
    if operator == 'in':
        if not isinstance(value, list) or not value:
            raise ValueError("une liste non vide est attendue pour l'opérateur 'in'")
        return column.in_(value)
    if operator == 'contains':
        return column.ilike(f"%{value}%")
    if operator == 'eq':
        return column == value
    if operator == 'ne':
        return column != value
    if operator == 'gt':
        return column > value
    if operator == 'gte':
        return column >= value
    if operator == 'lt':
        return column < value
    if operator == 'lte':
        return column <= value
    raise ValueError(f"opérateur inconnu : {operator}")


class FilterSchema(Schema):
    field = fields.String(required=True)
    operator = fields.String(required=True)
    value = fields.Raw(required=True)


class RunReportSchema(Schema):
    class Meta:
        # Un config sauvegardé porte aussi des clés purement frontend (chart_type...) —
        # ignorées ici plutôt que rejetées, seules filters/group_by/metric/dates sont interprétées.
        unknown = EXCLUDE

    start_date = fields.String(load_default=None, allow_none=True)
    end_date = fields.String(load_default=None, allow_none=True)
    filters = fields.List(fields.Nested(FilterSchema), load_default=list)
    group_by = fields.String(load_default='none')
    metric = fields.String(load_default='sum')


class SaveReportSchema(Schema):
    name = fields.String(required=True)
    config = fields.Dict(required=True)


class UpdateReportSchema(Schema):
    report_id = fields.UUID(required=True)
    name = fields.String(required=True)
    config = fields.Dict(required=True)


class CustomReportsRoutes:
    def __init__(self, app, DB, Users, CustomReports, Splits, Transactions, Accounts, Categories,
                 Tags, TagsOnSplits, Commodities, FxRates, UserSettings):
        ROUTE_PATH = f"{ROOT_PATH}/reports/custom"

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

        # Colonne réelle par champ de filtre — dépend des modèles injectés, donc résolue ici
        # plutôt que dans le dict FIELD_SPECS au niveau module.
        def _column_for(field):
            return {
                'account_id': Splits.account_id,
                'category_id': Transactions.category_id,
                'tag_id': TagsOnSplits.tag_id,
                'account_type': Accounts.account_type,
                'amount': Splits.quantity,
                'description': Transactions.description,
                'is_cleared': Transactions.is_cleared,
            }[field]

        def _dimension_expr(group_by):
            if group_by == 'category':
                return func.coalesce(Categories.name, 'Sans catégorie')
            if group_by == 'tag':
                return Tags.name
            if group_by == 'account':
                return Accounts.name
            if group_by in DATE_GROUPS:
                return func.date_trunc(group_by, Transactions.post_date)
            return None  # 'none'

        def _run_report(user_id, config):
            try:
                data = RunReportSchema().load(config)
            except ValidationError as err:
                raise ValueError(err.messages)

            group_by = data['group_by']
            metric = data['metric']
            if group_by not in GROUP_BY_OPTIONS:
                raise ValueError(f"regroupement inconnu : {group_by}")
            if metric not in METRIC_OPTIONS:
                raise ValueError(f"métrique inconnue : {metric}")

            today = date.today()
            try:
                start = date.fromisoformat(data['start_date']) if data['start_date'] else today - timedelta(days=365)
                end = date.fromisoformat(data['end_date']) if data['end_date'] else today
            except ValueError:
                raise ValueError("date invalide (format attendu : YYYY-MM-DD)")

            filters = data['filters']
            needs_tag_join = group_by == 'tag' or any(f['field'] == 'tag_id' for f in filters)
            account_type_filtered = any(f['field'] == 'account_type' for f in filters)

            dim_expr = _dimension_expr(group_by)
            select_cols = [Commodities.short_name, func.sum(Splits.quantity), func.count(Splits.id)]
            if dim_expr is not None:
                select_cols.insert(0, dim_expr)

            q = DB.session.query(*select_cols).select_from(Splits) \
                .join(Transactions, Splits.tx_id == Transactions.id) \
                .join(Accounts, Splits.account_id == Accounts.id) \
                .join(Commodities, Accounts.currency_id == Commodities.id) \
                .outerjoin(Categories, Transactions.category_id == Categories.id)
            if needs_tag_join:
                q = q.join(TagsOnSplits, TagsOnSplits.split_id == Splits.id) \
                     .join(Tags, Tags.id == TagsOnSplits.tag_id)

            q = q.filter(
                Transactions.user_id == user_id,
                Transactions.post_date >= start,
                Transactions.post_date <= end,
                Accounts.is_virtual == False,
                Accounts.is_hidden == False,
            )
            if not account_type_filtered:
                # Par défaut, seuls les comptes de valeur réelle — sinon les contreparties
                # Income/Expense du système à double entrée comptent deux fois le même mouvement.
                # Un filtre explicite sur account_type prend le pas sur cette restriction.
                q = q.filter(Accounts.account_type.in_(WEALTH_TYPES))

            for f in filters:
                field, operator, value = f['field'], f['operator'], f['value']
                spec = FIELD_SPECS.get(field)
                if not spec:
                    raise ValueError(f"champ de filtre inconnu : {field}")
                if operator not in spec['ops']:
                    raise ValueError(f"opérateur '{operator}' non autorisé pour le champ '{field}'")
                try:
                    if operator == 'in':
                        casted = [spec['cast'](v) for v in value]
                    elif operator == 'is_null':
                        casted = bool(value)
                    else:
                        casted = spec['cast'](value)
                except (ValueError, TypeError) as e:
                    raise ValueError(f"valeur invalide pour le filtre '{field}' : {e}")
                q = q.filter(_apply_operator(_column_for(field), operator, casted))

            if dim_expr is not None:
                q = q.group_by(dim_expr, Commodities.short_name)
            else:
                q = q.group_by(Commodities.short_name)

            target_currency = _target_currency(user_id)
            sums, counts = {}, {}
            for row in q.all():
                if dim_expr is not None:
                    dim_raw, code, qty_sum, n = row
                else:
                    dim_raw, code, qty_sum, n = 'Total', row[0], row[1], row[2]

                if group_by in DATE_GROUPS and dim_raw is not None:
                    label = dim_raw.strftime(DATE_GROUPS[group_by])
                else:
                    label = dim_raw if dim_raw is not None else 'Sans catégorie'

                converted = float(qty_sum or 0) * _rate_to(code, target_currency)
                sums[label] = sums.get(label, 0.0) + converted
                counts[label] = counts.get(label, 0) + int(n or 0)

            if metric == 'count':
                values_map = {k: v for k, v in counts.items()}
            elif metric == 'avg':
                values_map = {k: (sums[k] / counts[k] if counts[k] else 0.0) for k in sums}
            else:
                values_map = sums

            if group_by in DATE_GROUPS:
                labels = sorted(values_map.keys())
            else:
                labels = sorted(values_map.keys(), key=lambda k: -values_map[k])

            round_fn = (lambda v: round(v, 2)) if metric != 'count' else (lambda v: v)
            return {
                'labels': labels,
                'values': [round_fn(values_map[l]) for l in labels],
                'metric': metric,
                'group_by': group_by,
                'currency': target_currency,
                'start_date': str(start),
                'end_date': str(end),
            }

        @app.route(f"{ROUTE_PATH}/run", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def run_custom_report():
            user_id = get_jwt_identity()
            try:
                return json_response(_run_report(user_id, request.json or {}), HttpCode.OK)
            except ValueError as e:
                return json_response(str(e), HttpCode.BAD_REQUEST)

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def list_custom_reports():
            user_id = get_jwt_identity()
            reports = CustomReports.query.filter_by(user_id=user_id).order_by(CustomReports.created_at).all()
            return json_response([{
                'id': str(r.id), 'name': r.name, 'config': r.config,
                'created_at': r.created_at.isoformat() if r.created_at else None,
                'updated_at': r.updated_at.isoformat() if r.updated_at else None,
            } for r in reports], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def create_custom_report():
            try:
                data = SaveReportSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            try:
                _run_report(user_id, data['config'])  # valide la config avant de la persister
            except ValueError as e:
                return json_response(str(e), HttpCode.BAD_REQUEST)
            report = CustomReports(user_id=user_id, name=data['name'], config=data['config'])
            DB.session.add(report)
            DB.session.commit()
            return json_response({'id': str(report.id), 'name': report.name, 'config': report.config}, HttpCode.CREATED)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def update_custom_report():
            try:
                data = UpdateReportSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            report = CustomReports.query.filter_by(id=data['report_id'], user_id=user_id).first()
            if not report:
                return json_response('Rapport introuvable', HttpCode.NOT_FOUND)
            try:
                _run_report(user_id, data['config'])
            except ValueError as e:
                return json_response(str(e), HttpCode.BAD_REQUEST)
            report.name = data['name']
            report.config = data['config']
            DB.session.commit()
            return json_response({'id': str(report.id), 'name': report.name, 'config': report.config}, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, REPORTS_PERM)
        def delete_custom_report():
            report_id = request.args.get('report_id')
            if not report_id:
                return json_response('report_id requis', HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            report = CustomReports.query.filter_by(id=report_id, user_id=user_id).first()
            if not report:
                return json_response('Rapport introuvable', HttpCode.NOT_FOUND)
            DB.session.delete(report)
            DB.session.commit()
            return json_response('Rapport supprimé', HttpCode.OK)
