import uuid
from datetime import datetime, date
from decimal import Decimal

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.market_price import fetch_live_price, convert_amount, get_fx_rate
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.portfolio_ops import resolve_current_value, resolve_purchase_price, resolve_split_amounts, \
    convert_asset_to_default_currency, convert_default_to_asset_currency, format_qty, cost_basis_per_unit
from backend.utils.asset_geography import compute_country_breakdown
from backend.utils.wealth import compute_bank_net_worth, get_portfolio_breakdown

VALID_ASSET_TYPES = ('Stock', 'ETF', 'RealEstate', 'Vehicle', 'Other')
ASSETS_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']


class AddAssetSchema(Schema):
    symbol = fields.String(required=True)
    name = fields.String(required=True)
    asset_type = fields.String(required=True, validate=validate.OneOf(VALID_ASSET_TYPES))
    sector = fields.String(load_default=None)
    country = fields.String(load_default=None, allow_none=True)
    commodity_id = fields.UUID(required=True)
    value_per_unit = fields.Decimal(load_default=0, as_string=False)
    track_live_price = fields.Boolean(load_default=False)


class UpdateAssetSchema(Schema):
    asset_id = fields.UUID(required=True)
    symbol = fields.String(required=True)
    name = fields.String(required=True)
    asset_type = fields.String(required=True, validate=validate.OneOf(VALID_ASSET_TYPES))
    sector = fields.String(load_default=None)
    country = fields.String(load_default=None, allow_none=True)
    commodity_id = fields.UUID(required=True)
    value_per_unit = fields.Decimal(load_default=0, as_string=False)
    track_live_price = fields.Boolean(load_default=False)


class DeleteAssetSchema(Schema):
    asset_id = fields.UUID(required=True)


class RefreshAssetPriceSchema(Schema):
    asset_id = fields.UUID(required=True)


class AddPossessionSchema(Schema):
    asset_id = fields.UUID(required=True)
    account_id = fields.UUID(required=True)
    source_account_id = fields.UUID(load_default=None)
    quantity = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    purchase_price = fields.Decimal(required=True, as_string=False)
    # Forfait, pas un prix unitaire — toujours saisi dans la devise par défaut de l'utilisateur
    # (Settings.currency), quelle que soit la devise de l'actif ou du compte débité.
    fees = fields.Decimal(load_default=Decimal('0'), as_string=False, validate=validate.Range(min=0))
    # Saisi par l'utilisateur quand l'actif n'est PAS dans la devise par défaut (ex: titre coté en
    # USD, devise par défaut EUR) : 1 unité de la devise de l'actif = fx_rate unité(s) de la devise
    # par défaut. Remplace la résolution automatique du taux historique pour cette conversion
    # (potentiellement imprécise/indisponible) par le taux réellement appliqué par le courtier/la
    # banque. Indépendant du compte débité choisi — voir portfolio_ops.py::convert_asset_to_default_currency.
    fx_rate = fields.Decimal(load_default=None, as_string=False, allow_none=True, validate=validate.Range(min=Decimal('0.000001')))
    purchase_date = fields.Date(required=True)


class UpdatePossessionSchema(Schema):
    possession_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    purchase_price = fields.Decimal(required=True, as_string=False)
    fees = fields.Decimal(load_default=Decimal('0'), as_string=False, validate=validate.Range(min=0))
    fx_rate = fields.Decimal(load_default=None, as_string=False, allow_none=True, validate=validate.Range(min=Decimal('0.000001')))
    purchase_date = fields.Date(required=True)


class DeletePossessionSchema(Schema):
    possession_id = fields.UUID(required=True)


class SellPossessionSchema(Schema):
    # Vente au niveau de l'actif (dans un compte donné), pas d'une ligne précise — les lots sont
    # consommés automatiquement en FIFO (le plus ancien d'abord), voir sell_possession ci-dessous.
    asset_id = fields.UUID(required=True)
    account_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    sale_price = fields.Decimal(required=True, as_string=False)  # devise native si track_live_price, miroir purchase_price
    # Toujours en devise par défaut (comme AddPossessionSchema.fees) ; fx_rate même convention que
    # AddPossessionSchema.fx_rate (actif → devise par défaut), utilisé ici pour ramener le produit
    # de la vente et pour reconvertir les frais/la plus-value dans la devise de l'actif.
    fees = fields.Decimal(load_default=Decimal('0'), as_string=False, validate=validate.Range(min=0))
    fx_rate = fields.Decimal(load_default=None, as_string=False, allow_none=True, validate=validate.Range(min=Decimal('0.000001')))
    sale_date = fields.Date(required=True)
    dest_account_id = fields.UUID(load_default=None)


class UpdateSaleSchema(Schema):
    # asset_id/account_id ne sont pas éditables (déduits des cessions existantes) — même logique que
    # UpdatePossessionSchema, qui ne laisse pas non plus changer le compte d'une position.
    sale_id = fields.UUID(required=True)
    quantity = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    sale_price = fields.Decimal(required=True, as_string=False)
    fees = fields.Decimal(load_default=Decimal('0'), as_string=False, validate=validate.Range(min=0))
    fx_rate = fields.Decimal(load_default=None, as_string=False, allow_none=True, validate=validate.Range(min=Decimal('0.000001')))
    sale_date = fields.Date(required=True)
    dest_account_id = fields.UUID(load_default=None)


class DeleteSaleSchema(Schema):
    sale_id = fields.UUID(required=True)


class CreateAssetOperationSchema(Schema):
    asset_id = fields.UUID(required=True)
    operation_type = fields.String(required=True, validate=validate.OneOf(['split', 'merger', 'spinoff']))
    operation_date = fields.Date(required=True)
    # "Pour ratio_from part(s) détenue(s), on obtient ratio_to part(s)" — ex: split 4-pour-1 =>
    # ratio_from=1, ratio_to=4 ; regroupement 1-pour-10 => ratio_from=10, ratio_to=1.
    ratio_from = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    ratio_to = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=Decimal('0.000001')))
    # Obligatoire pour merger/spinoff (validé dans la route, pas ici : dépend de operation_type).
    # L'actif cible doit déjà exister — pas de création inline dans cette opération.
    target_asset_id = fields.UUID(load_default=None, allow_none=True)
    # Obligatoire pour spinoff uniquement (part du prix de revient transférée vers l'actif cible).
    cost_allocation_pct = fields.Decimal(load_default=None, allow_none=True, validate=validate.Range(min=0, max=100))
    note = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=255))


class GetAssetOperationsSchema(Schema):
    asset_id = fields.UUID(required=True)


class GetAssetHistorySchema(Schema):
    asset_id = fields.UUID(required=True)
    start_date = fields.Date(load_default=None)
    end_date = fields.Date(load_default=None)
    currency = fields.String(load_default='EUR')


class GetValuationsSchema(Schema):
    asset_id = fields.UUID(required=True)


class AddValuationSchema(Schema):
    asset_id = fields.UUID(required=True)
    valuation_date = fields.Date(required=True)
    value_per_unit = fields.Decimal(required=True, as_string=False)


class UpdateValuationSchema(Schema):
    valuation_id = fields.UUID(required=True)
    valuation_date = fields.Date(required=True)
    value_per_unit = fields.Decimal(required=True, as_string=False)


class DeleteValuationSchema(Schema):
    valuation_id = fields.UUID(required=True)


def _asset_to_dict(a):
    return {
        'id': str(a.id),
        'symbol': a.symbol,
        'name': a.name,
        'asset_type': a.asset_type,
        'sector': a.sector,
        'country': a.country,
        'commodity_id': str(a.commodity_id),
        'value_per_unit': float(a.value_per_unit or 0),
        'track_live_price': a.track_live_price,
        'last_price_updated_at': a.last_price_updated_at.isoformat() if a.last_price_updated_at else None,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    }


def _compute_geography(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, user_id, target_currency):
    """Répartition géographique du portefeuille : actions/ETF via Yahoo Finance (pays direct pour une
    action, extrapolation du top 10 holdings pour un ETF — Yahoo ne fournit jamais la composition
    complète d'un fonds, voir asset_geography.py), actifs physiques (RealEstate/Vehicle/Other) via le
    pays saisi manuellement sur l'actif (100% de sa valeur, un seul pays par actif contrairement à un
    ETF). Extrait de get_assets_geography (route GET /assets/geography) pour être réutilisé par
    l'endpoint de diversification sans dupliquer les appels Yahoo Finance."""
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}

    def asset_value(a):
        possessions = AssetPossession.query.filter(AssetPossession.asset_id == a.id).all()
        possession_ids = [p.id for p in possessions]
        disposals = (AssetDisposal.query.filter(AssetDisposal.possession_id.in_(possession_ids)).all()
                     if possession_ids else [])
        disposed_by_possession = {}
        for disp in disposals:
            disposed_by_possession.setdefault(disp.possession_id, []).append(disp)

        total_qty = float(sum(p.quantity - sum(d.quantity for d in disposed_by_possession.get(p.id, []))
                               for p in possessions))
        if total_qty <= 0:
            return None
        total_value = total_qty * float(a.value_per_unit or 0)
        native_commodity = commodities_by_id.get(a.commodity_id)
        native_code = native_commodity.short_name if native_commodity else target_currency
        rate = 1.0 if native_code == target_currency else (get_fx_rate(native_code, target_currency, FxRates) or 1.0)
        return total_value * rate

    assets = Assets.query.filter(Assets.user_id == user_id).all()

    positions = []
    by_country = {}
    unmapped_value = 0.0
    for a in assets:
        value = asset_value(a)
        if value is None:
            continue
        if a.asset_type in ('Stock', 'ETF'):
            positions.append({'symbol': a.symbol, 'asset_type': a.asset_type, 'value': value})
        elif a.country:
            by_country[a.country] = by_country.get(a.country, 0.0) + value
        else:
            unmapped_value += value

    breakdown = compute_country_breakdown(positions)
    for country, value in breakdown['by_country'].items():
        by_country[country] = by_country.get(country, 0.0) + value
    unmapped_value += breakdown['unmapped_value']
    total_known_value = sum(by_country.values())
    grand_total = total_known_value + unmapped_value

    countries = sorted((
        {'country': country, 'value': round(value, 2),
         'percent': round(value / total_known_value * 100, 2) if total_known_value else 0}
        for country, value in by_country.items()
    ), key=lambda c: c['percent'], reverse=True)

    return {
        'countries': countries,
        'by_country_raw': by_country,
        'total_known_value': round(total_known_value, 2),
        'unmapped_value': round(unmapped_value, 2),
        'unmapped_percent': round(unmapped_value / grand_total * 100, 2) if grand_total else 0,
    }


def _diversification_score(values):
    """Score de diversification 0-100 pour un ensemble de montants (une dimension : classe d'actif,
    secteur ou pays) basé sur l'indice de Herfindahl-Hirschman (HHI = somme des parts au carré,
    mesure standard de concentration en finance/économie). HHI vaut 1/N pour N parts égales (parfaite
    diversification) et 1 pour une concentration totale sur une seule part — score = 100*(1-HHI),
    donc 0 = tout sur une seule part, proche de 100 = très étalé sur beaucoup de parts égales.
    None (pas de score, pas de matière) si aucune valeur positive."""
    total = sum(v for v in values if v > 0)
    if total <= 0:
        return None
    hhi = sum((v / total) ** 2 for v in values if v > 0)
    return round((1 - hhi) * 100, 1)


def _possession_to_dict(p, disposals=None):
    disposals = disposals or []
    disposed_qty = sum(d.quantity for d in disposals)
    return {
        'id': str(p.id),
        'asset_id': str(p.asset_id),
        'account_id': str(p.account_id),
        'source_account_id': str(p.source_account_id) if p.source_account_id else None,
        'tx_id': str(p.tx_id) if p.tx_id else None,
        'dca_plan_id': str(p.dca_plan_id) if p.dca_plan_id else None,
        'operation_id': str(p.operation_id) if p.operation_id else None,
        'quantity': float(p.quantity),
        'remaining_quantity': float(p.quantity - disposed_qty),
        'purchase_price': float(p.purchase_price) if p.purchase_price is not None else None,
        'purchase_price_native': float(p.purchase_price_native) if p.purchase_price_native is not None else None,
        'fees': float(p.fees or 0),
        'fx_rate': float(p.fx_rate) if p.fx_rate is not None else None,
        'purchase_date': p.purchase_date.isoformat() if p.purchase_date else None,
        'created_at': p.created_at.isoformat() if p.created_at else None,
        'disposals': [{
            'id': str(d.id), 'quantity': float(d.quantity),
            'sale_date': d.sale_date.isoformat() if d.sale_date else None,
            'sale_price': float(d.sale_price) if d.sale_price is not None else None,
            'fees': float(d.fees or 0),
            'fx_rate': float(d.fx_rate) if d.fx_rate is not None else None,
            'dest_account_id': str(d.dest_account_id) if d.dest_account_id else None,
            'realized_gain': float(d.realized_gain) if d.realized_gain is not None else None,
            'operation_id': str(d.operation_id) if d.operation_id else None,
            'sale_id': str(d.sale_id) if d.sale_id else None,
        } for d in disposals],
    }


def _operation_to_dict(o):
    return {
        'id': str(o.id),
        'asset_id': str(o.asset_id),
        'operation_type': o.operation_type,
        'operation_date': o.operation_date.isoformat(),
        'ratio_from': float(o.ratio_from),
        'ratio_to': float(o.ratio_to),
        'target_asset_id': str(o.target_asset_id) if o.target_asset_id else None,
        'cost_allocation_pct': float(o.cost_allocation_pct) if o.cost_allocation_pct is not None else None,
        'note': o.note,
        'created_at': o.created_at.isoformat() if o.created_at else None,
    }


def _valuation_to_dict(v):
    return {
        'id': str(v.id),
        'asset_id': str(v.asset_id),
        'valuation_date': v.valuation_date.isoformat(),
        'value_per_unit': float(v.value_per_unit),
        'created_at': v.created_at.isoformat() if v.created_at else None,
    }


def _sync_asset_value_per_unit(AssetValuations, asset):
    """Après ajout/édition/suppression d'une valorisation manuelle : Assets.value_per_unit doit
    refléter la valorisation la plus récente, puisque c'est ce champ qui sert de "valeur actuelle"
    partout ailleurs dans l'app (dashboard, breakdown du portefeuille, snapshot du jour). Si plus
    aucune valorisation n'existe, on laisse value_per_unit tel quel (comportement historique)."""
    latest = AssetValuations.query.filter_by(asset_id=asset.id).order_by(AssetValuations.valuation_date.desc()).first()
    if latest:
        asset.value_per_unit = latest.value_per_unit


def _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits,
                           WealthSnapshot, AssetValuations, user_id, from_date):
    """Supprime les snapshots de patrimoine existants à partir de from_date pour cet utilisateur puis
    les reconstruit immédiatement — appelé après ajout/modification/suppression d'une position (ou
    d'une valorisation manuelle) dont la date affecte l'historique, pour ne pas attendre le prochain
    cycle planifié (24h)."""
    from backend.utils.wealth import backfill_wealth_history
    from backend.scheduler import snapshot_wealth
    WealthSnapshot.query.filter(
        WealthSnapshot.user_id == user_id,
        WealthSnapshot.snapshot_date >= from_date,
    ).delete()
    DB.session.commit()
    # Scopé à CET utilisateur (voir user_id/snapshot_user_id) — recalculer tout le monde à chaque
    # achat/vente/suppression de position serait un gaspillage inutile et un contributeur direct de
    # la latence perçue sur ces actions (voir docstring de backfill_wealth_history/snapshot_wealth).
    backfill_wealth_history(DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations, user_id=user_id)
    snapshot_wealth(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, WealthSnapshot, Splits, snapshot_user_id=user_id)


class _OperationError(Exception):
    """Erreur métier levée en cours d'application d'une opération sur titre, ou de la création/
    modification d'une vente (voir _execute_sale) — distincte d'une Exception générique pour renvoyer
    un BAD_REQUEST (message utilisateur) plutôt qu'un SERVER_ERROR, tout en garantissant le rollback
    (contrairement à un `return` en plein milieu du try). `response` permet de propager tel quel un
    json_response déjà construit par un helper de portfolio_ops.py (son code HTTP n'est pas toujours
    BAD_REQUEST) sans le reconstruire à partir d'un message."""
    def __init__(self, message=None, code=HttpCode.BAD_REQUEST, response=None):
        super().__init__(message or 'Operation error')
        self.message = message
        self.code = code
        self.response = response


def _execute_sale(DB, Assets, AssetPossession, AssetDisposal, Commodities, Accounts, Transactions, Splits,
                   UserSettings, FxRates, user_id, asset_id, account_id, quantity, sale_price_native,
                   sale_date, fees, dest_account_id, manual_fx_rate, sale_id):
    """Cœur FIFO partagé par la création d'une vente (route POST) et sa modification (route PATCH) —
    voir AssetsRoutes.sell_possession/update_sale. Consomme les lots de (asset_id, account_id) du
    plus ancien au plus récent jusqu'à couvrir `quantity`, crée les AssetDisposal (et la Transaction/
    Splits si dest_account_id est fourni) — ajoutés à la session mais PAS commités, à la charge de
    l'appelant (une modification supprime d'abord l'ancienne vente dans la même transaction). Lève
    _OperationError sur toute erreur de validation métier plutôt que de retourner une réponse Flask
    directement, pour rester utilisable par n'importe quelle route appelante."""
    a = Assets.query.filter(Assets.id == asset_id, Assets.user_id == user_id).first()
    if not a:
        raise _OperationError('Asset not found', HttpCode.NOT_FOUND)
    commodity = Commodities.query.filter_by(id=a.commodity_id).first()
    if not commodity:
        raise _OperationError('Commodity not found', HttpCode.NOT_FOUND)
    position_account = Accounts.query.filter(
        Accounts.id == account_id, Accounts.user_id == user_id).first()
    if not position_account:
        raise _OperationError('Account not found', HttpCode.NOT_FOUND)

    # FIFO : lots de ce (actif, compte), du plus ancien au plus récent, avec leur quantité restante —
    # consommés dans cet ordre jusqu'à couvrir la quantité vendue. Méthode standard pour le calcul de
    # plus-value (cohérent avec le fisc français), et celle qu'un utilisateur attend implicitement
    # quand il vend "l'actif" plutôt qu'une ligne précise.
    lots = AssetPossession.query.filter_by(
        user_id=user_id, asset_id=asset_id, account_id=account_id
    ).order_by(AssetPossession.purchase_date.asc(), AssetPossession.created_at.asc()).all()
    disposals_by_lot = {p.id: AssetDisposal.query.filter_by(possession_id=p.id).all() for p in lots}
    chunks = []  # (lot, quantité prélevée sur ce lot)
    remaining_to_sell = float(quantity)
    for p in lots:
        if remaining_to_sell <= 0:
            break
        already_sold = sum(float(d.quantity) for d in disposals_by_lot[p.id])
        lot_remaining = float(p.quantity) - already_sold
        if lot_remaining <= 0:
            continue
        take = min(lot_remaining, remaining_to_sell)
        chunks.append((p, take))
        remaining_to_sell -= take
    if remaining_to_sell > 1e-9:
        total_remaining = sum(float(p.quantity) - sum(float(d.quantity) for d in disposals_by_lot[p.id]) for p in lots)
        raise _OperationError(
            f"Quantité vendue ({quantity}) supérieure à la quantité détenue sur ce compte ({total_remaining})")

    sale_price_native = float(sale_price_native)
    sale_price = sale_price_native
    if a.track_live_price:
        sale_price, error = resolve_purchase_price(
            a.symbol, commodity.short_name, sale_price_native, sale_date, FxRates)
        if error:
            raise _OperationError(response=error)

    dest_account = None
    if dest_account_id:
        dest_account = Accounts.query.filter(
            Accounts.id == dest_account_id, Accounts.user_id == user_id).first()
        if not dest_account:
            raise _OperationError('Destination account not found', HttpCode.NOT_FOUND)
        if dest_account.account_type not in ('Current', 'Assets', 'Equity'):
            raise _OperationError("Le compte crédité doit être de type 'Current', 'Assets' ou 'Equity'")

    settings = UserSettings.query.filter_by(user_id=user_id).first()
    default_currency = settings.currency if settings else 'EUR'

    total_fees = float(fees)
    total_quantity = float(quantity)

    # Résolu (et persisté plus bas dans chaque disposal.fx_rate) que la vente ait ou non un compte
    # crédité — c'est ce même taux qui sert à reconvertir les frais de CETTE vente (déjà en devise
    # par défaut) vers la devise de l'actif, pour rester cohérent avec sale_price/purchase_price/
    # realized_gain qui y restent exprimés (cf. rt_tax.py qui reconvertit lui-même realized_gain
    # depuis commodity.short_name).
    proceeds_asset_ccy = total_quantity * float(sale_price)
    proceeds_default, resolved_fx_rate, error = convert_asset_to_default_currency(
        proceeds_asset_ccy, commodity.short_name, default_currency, manual_fx_rate, sale_date, FxRates)
    if error:
        raise _OperationError(response=error)
    if commodity.short_name == default_currency:
        total_fees_asset_ccy = total_fees
        resolved_fx_rate = None  # pas "1.0" : aucune conversion n'a de sens ici (même devise)
    else:
        total_fees_asset_ccy = total_fees / resolved_fx_rate

    # Frais d'achat de chaque lot reconvertis avec LE TAUX ET LA DATE DE CE LOT (p.fx_rate /
    # p.purchase_date), pas ceux de la vente en cours — un même lot peut être vendu des années après
    # avoir été acheté à un taux différent.
    buy_fees_asset_ccy_by_lot = {}
    for p, take in chunks:
        prorated_buy_fees_default = float(p.fees or 0) * (take / float(p.quantity))
        lot_purchase_date = p.purchase_date.date() if hasattr(p.purchase_date, 'date') else p.purchase_date
        prorated_buy_fees_asset, error = convert_default_to_asset_currency(
            prorated_buy_fees_default, commodity.short_name, default_currency, p.fx_rate,
            lot_purchase_date, FxRates)
        if error:
            raise _OperationError(response=error)
        buy_fees_asset_ccy_by_lot[p.id] = prorated_buy_fees_asset

    dest_amount = source_amount = dest_fx_rate = None
    if dest_account:
        # Le produit de la vente (déjà ramené en devise par défaut ci-dessus) moins les frais (déjà
        # en devise par défaut) donne le virement réellement reçu — comme chez un courtier, symétrique
        # de l'ajout des frais au coût dans add_possession. Un seul virement pour la vente entière,
        # même si elle pioche sur plusieurs lots (FIFO) — les frais/le gain ne sont ventilés par lot
        # que pour le calcul du gain réalisé, pas pour l'écriture comptable.
        total_proceeds_default = proceeds_default - total_fees
        if total_proceeds_default < 0:
            raise _OperationError("Les frais dépassent le montant de la vente")
        # Rôles inversés par rapport à add_possession : ici "dest_account" est le compte crédité (le
        # cash qui entre), "source_account" est le compte débité (la position qui sort) — cf.
        # décision de conception Phase 2 (vente = renversement à 2 splits, au montant de la vente,
        # pas au coût d'achat).
        dest_amount, source_amount, dest_fx_rate, error = resolve_split_amounts(
            Accounts, Commodities, dest_account, position_account, total_proceeds_default,
            default_currency, sale_date, FxRates)
        if error:
            raise _OperationError(response=error)

    tx = None
    source_split_id = dest_split_id = None
    if dest_account:
        tx = Transactions(
            user_id=user_id,
            currency_id=position_account.currency_id,
            post_date=sale_date,
            effective_date=sale_date,
            description=f"Vente {a.symbol} x{format_qty(quantity)}",
            category_id=None,
            is_cleared=True,
        )
        DB.session.add(tx)
        DB.session.flush()
        source_split_id, dest_split_id = uuid.uuid4(), uuid.uuid4()
        # source = compte de la position (débité, les titres "sortent") ; dest = compte crédité (le
        # cash entre) — voir commentaire ci-dessus sur l'inversion des rôles.
        DB.session.add(Splits(id=source_split_id, tx_id=tx.id, account_id=position_account.id, quantity=-source_amount, fx_rate=1.0))
        DB.session.add(Splits(id=dest_split_id, tx_id=tx.id, account_id=dest_account.id, quantity=dest_amount, fx_rate=dest_fx_rate))
        DB.session.flush()

    disposals = []
    for p, take in chunks:
        # Frais de vente et gain ventilés au prorata de la part de CETTE vente prélevée sur ce lot ;
        # frais d'achat du lot proratisés à la quantité prélevée sur ce lot spécifiquement (un même
        # lot peut être vendu en plusieurs fois au fil du temps). chunk_fees_default est stocké tel
        # quel (devise par défaut, comme AssetPossession.fees) ; chunk_fees_asset_ccy (reconverti
        # plus haut) sert uniquement au calcul du gain.
        fraction = take / total_quantity
        chunk_fees_default = total_fees * fraction
        chunk_fees_asset_ccy = total_fees_asset_ccy * fraction
        realized_gain = None
        if p.purchase_price is not None:
            realized_gain = (
                (float(sale_price) - float(p.purchase_price)) * take
                - chunk_fees_asset_ccy - buy_fees_asset_ccy_by_lot[p.id]
            )
        holding_period_days = None
        if p.purchase_date:
            purchase_date_only = p.purchase_date.date() if hasattr(p.purchase_date, 'date') else p.purchase_date
            holding_period_days = (sale_date - purchase_date_only).days

        disposal = AssetDisposal(
            user_id=user_id,
            possession_id=p.id,
            quantity=take,
            sale_price=sale_price,
            sale_price_native=sale_price_native,
            fees=chunk_fees_default,
            fx_rate=resolved_fx_rate,
            sale_date=sale_date,
            dest_account_id=dest_account_id,
            tx_id=tx.id if tx else None,
            source_split_id=source_split_id,
            dest_split_id=dest_split_id,
            realized_gain=realized_gain,
            holding_period_days=holding_period_days,
            sale_id=sale_id,
        )
        DB.session.add(disposal)
        disposals.append(disposal)

    return a, position_account, disposals


class AssetsRoutes:
    def __init__(self, app, DB, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Accounts, Transactions, Splits, WealthSnapshot, Users, AssetValuations, UserSettings, AssetOperations):
        ROUTE_PATH = f"{ROOT_PATH}/assets"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_assets():
            user_id = get_jwt_identity()
            # `value_per_unit`/`total_value` restent dans la devise native de l'actif (nécessaire
            # pour l'édition et le calcul de plus-value par lot) ; `converted_*` est ajouté pour
            # l'affichage liste, dans la devise par défaut de l'utilisateur (cf. Dashboard/Reports
            # qui font déjà cette conversion — Portfolio.vue affichait jusqu'ici uniquement la
            # devise native, ce qui restait en USD/etc. même après changement de devise par défaut).
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            target_currency = settings.currency if settings else 'EUR'
            commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}

            assets = Assets.query.filter(Assets.user_id == user_id).order_by(Assets.name).all()
            result = []
            for a in assets:
                possessions = AssetPossession.query.filter(AssetPossession.asset_id == a.id).all()
                possession_ids = [p.id for p in possessions]
                disposals = (AssetDisposal.query.filter(AssetDisposal.possession_id.in_(possession_ids)).all()
                             if possession_ids else [])
                disposals_by_possession = {}
                for disp in disposals:
                    disposals_by_possession.setdefault(disp.possession_id, []).append(disp)

                total_qty = float(sum(p.quantity - sum(d.quantity for d in disposals_by_possession.get(p.id, []))
                                       for p in possessions))
                total_value = round(total_qty * float(a.value_per_unit or 0), 2)
                native_commodity = commodities_by_id.get(a.commodity_id)
                native_code = native_commodity.short_name if native_commodity else target_currency
                rate = 1.0 if native_code == target_currency else (get_fx_rate(native_code, target_currency, FxRates) or 1.0)
                d = _asset_to_dict(a)
                d['total_quantity'] = total_qty
                d['total_value'] = total_value
                d['display_currency'] = target_currency
                d['converted_value_per_unit'] = round(float(a.value_per_unit or 0) * rate, 4)
                d['converted_total_value'] = round(total_value * rate, 2)
                d['possessions'] = [_possession_to_dict(p, disposals_by_possession.get(p.id, [])) for p in possessions]
                result.append(d)
            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/geography", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_assets_geography():
            user_id = get_jwt_identity()
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            target_currency = settings.currency if settings else 'EUR'
            geo = _compute_geography(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, user_id, target_currency)
            return json_response({
                'countries': geo['countries'],
                'total_known_value': geo['total_known_value'],
                'unmapped_value': geo['unmapped_value'],
                'unmapped_percent': geo['unmapped_percent'],
                'display_currency': target_currency,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/diversification", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_assets_diversification():
            """Portail de diversification du patrimoine global (bancaire + portefeuille + physique) :
            répartition par classe d'actif, par secteur et par pays, chacune avec un score 0-100
            (voir _diversification_score), plus une note globale = moyenne des trois. Contrairement à
            GET /assets/geography (portefeuille seul), le périmètre ici est le patrimoine total — le
            cash et l'immobilier comptent comme des parts à part entière de chaque dimension pertinente,
            pas seulement les lignes du portefeuille financier."""
            user_id = get_jwt_identity()
            settings = UserSettings.query.filter_by(user_id=user_id).first()
            target_currency = settings.currency if settings else 'EUR'

            bank_cash = compute_bank_net_worth(Accounts, Commodities, AssetPossession, FxRates, user_id, target_currency)
            portfolio = get_portfolio_breakdown(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, user_id, target_currency)

            # --- Classe d'actif : cash + chaque type d'actif détenu, sur le patrimoine total ---
            class_values = {'Cash / Épargne': bank_cash} if bank_cash > 0 else {}
            asset_type_labels = {'Stock': 'Actions', 'ETF': 'ETF', 'RealEstate': 'Immobilier',
                                  'Vehicle': 'Véhicules', 'Other': 'Autre'}
            for a in portfolio:
                label = asset_type_labels.get(a['asset_type'], a['asset_type'])
                class_values[label] = class_values.get(label, 0) + a['value']
            class_total = sum(class_values.values())
            asset_class = {
                'buckets': sorted((
                    {'label': label, 'value': round(v, 2), 'percent': round(v / class_total * 100, 2) if class_total else 0}
                    for label, v in class_values.items() if v > 0
                ), key=lambda b: b['percent'], reverse=True),
                'score': _diversification_score(class_values.values()),
            }

            # --- Secteur : chaque secteur d'actions/ETF détenu, le reste du patrimoine (cash +
            # immobilier + actifs sans secteur identifié) formant un seul bloc "Hors actions/ETF" —
            # un portefeuille 90% cash / 10% actions ne doit pas paraître bien diversifié juste parce
            # que ces 10% couvrent beaucoup de secteurs (voir périmètre "patrimoine global" demandé). ---
            sector_values = {}
            outside_equities = bank_cash if bank_cash > 0 else 0
            for a in portfolio:
                if a['asset_type'] in ('Stock', 'ETF') and a['sector']:
                    sector_values[a['sector']] = sector_values.get(a['sector'], 0) + a['value']
                else:
                    outside_equities += a['value']
            if outside_equities > 0:
                sector_values['Hors actions/ETF (cash, immobilier…)'] = outside_equities
            sector_total = sum(sector_values.values())
            sector = {
                'buckets': sorted((
                    {'label': label, 'value': round(v, 2), 'percent': round(v / sector_total * 100, 2) if sector_total else 0}
                    for label, v in sector_values.items() if v > 0
                ), key=lambda b: b['percent'], reverse=True),
                'score': _diversification_score(sector_values.values()),
            }

            # --- Géographie : réutilise le calcul de /assets/geography (financier + physique), le
            # cash s'ajoutant comme un bloc "non localisé" au même titre que le reste non identifié —
            # aucune notion fiable de pays pour un simple solde bancaire dans ce modèle de données. ---
            geo = _compute_geography(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, user_id, target_currency)
            geo_values = dict(geo['by_country_raw'])
            geo_unmapped = geo['unmapped_value'] + (bank_cash if bank_cash > 0 else 0)
            if geo_unmapped > 0:
                geo_values['Non localisé (cash…)'] = geo_values.get('Non localisé (cash…)', 0) + geo_unmapped
            geo_total = sum(geo_values.values())
            geography = {
                'buckets': sorted((
                    {'label': label, 'value': round(v, 2), 'percent': round(v / geo_total * 100, 2) if geo_total else 0}
                    for label, v in geo_values.items() if v > 0
                ), key=lambda b: b['percent'], reverse=True),
                'score': _diversification_score(geo_values.values()),
            }

            dimension_scores = [d['score'] for d in (asset_class, sector, geography) if d['score'] is not None]
            global_score = round(sum(dimension_scores) / len(dimension_scores), 1) if dimension_scores else None

            return json_response({
                'asset_class': asset_class,
                'sector': sector,
                'geography': geography,
                'global_score': global_score,
                'total_patrimoine': round(class_total, 2),
                'display_currency': target_currency,
            }, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def add_asset():
            try:
                data = AddAssetSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            if data['track_live_price']:
                commodity = Commodities.query.filter_by(id=data['commodity_id']).first()
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                value_per_unit, error = resolve_current_value(data['symbol'], commodity.short_name, FxRates)
                if error:
                    return error
                last_price_updated_at = datetime.now()
            else:
                value_per_unit = data.get('value_per_unit', 0)
                last_price_updated_at = None

            try:
                a = Assets(
                    user_id=get_jwt_identity(),
                    symbol=data['symbol'],
                    name=data['name'],
                    asset_type=data['asset_type'],
                    sector=data.get('sector') if data['asset_type'] in ('Stock', 'ETF') else None,
                    country=data.get('country') if data['asset_type'] not in ('Stock', 'ETF') else None,
                    commodity_id=data['commodity_id'],
                    value_per_unit=value_per_unit,
                    track_live_price=data['track_live_price'],
                    last_price_updated_at=last_price_updated_at,
                )
                DB.session.add(a)
                DB.session.commit()
                return json_response(_asset_to_dict(a), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def update_asset():
            try:
                data = UpdateAssetSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == get_jwt_identity()).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            if data['track_live_price']:
                commodity = Commodities.query.filter_by(id=data['commodity_id']).first()
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                value_per_unit, error = resolve_current_value(data['symbol'], commodity.short_name, FxRates)
                if error:
                    return error
                last_price_updated_at = datetime.now()
            else:
                value_per_unit = data.get('value_per_unit', 0)
                last_price_updated_at = None

            try:
                a.symbol = data['symbol']
                a.name = data['name']
                a.asset_type = data['asset_type']
                a.sector = data.get('sector') if data['asset_type'] in ('Stock', 'ETF') else None
                a.country = data.get('country') if data['asset_type'] not in ('Stock', 'ETF') else None
                a.commodity_id = data['commodity_id']
                a.value_per_unit = value_per_unit
                a.track_live_price = data['track_live_price']
                a.last_price_updated_at = last_price_updated_at
                DB.session.commit()
                return json_response(_asset_to_dict(a), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def delete_asset():
            try:
                data = DeleteAssetSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == get_jwt_identity()).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            try:
                DB.session.delete(a)
                DB.session.commit()
                return json_response('Asset deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/refresh-price", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def refresh_asset_price():
            try:
                data = RefreshAssetPriceSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == get_jwt_identity()).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            if not a.track_live_price:
                return json_response("Cet actif n'est pas suivi en temps réel", HttpCode.BAD_REQUEST)
            commodity = Commodities.query.filter_by(id=a.commodity_id).first()
            if not commodity:
                return json_response('Commodity not found', HttpCode.NOT_FOUND)
            value_per_unit, error = resolve_current_value(a.symbol, commodity.short_name, FxRates)
            if error:
                return error
            try:
                a.value_per_unit = value_per_unit
                a.last_price_updated_at = datetime.now()
                DB.session.commit()
                return json_response(_asset_to_dict(a), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        # ── Historique & valorisations manuelles ────────────────────────────

        @app.route(f"{ROUTE_PATH}/history", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_asset_history():
            try:
                data = GetAssetHistorySchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            end_date = data['end_date'] or date.today()
            start_date = data['start_date']
            if not start_date:
                possessions = AssetPossession.query.filter_by(asset_id=a.id).all()
                candidates = [p.purchase_date.date() if p.purchase_date else p.created_at.date() for p in possessions]
                candidates += [v.valuation_date for v in AssetValuations.query.filter_by(asset_id=a.id).all()]
                start_date = min(candidates) if candidates else end_date

            from backend.utils.wealth import asset_value_series
            history = asset_value_series(
                Assets, AssetPossession, AssetDisposal, Commodities, FxRates, AssetValuations,
                a, start_date, end_date, data['currency'].upper())
            return json_response(history, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_valuations():
            try:
                data = GetValuationsSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            valuations = AssetValuations.query.filter_by(asset_id=a.id).order_by(AssetValuations.valuation_date).all()
            return json_response([_valuation_to_dict(v) for v in valuations], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def add_valuation():
            try:
                data = AddValuationSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            if a.track_live_price:
                return json_response("Cet actif suit un cours live, pas de saisie manuelle possible", HttpCode.BAD_REQUEST)
            if AssetValuations.query.filter_by(asset_id=a.id, valuation_date=data['valuation_date']).first():
                return json_response('Une valorisation existe déjà à cette date', HttpCode.CONFLICT)
            try:
                v = AssetValuations(
                    user_id=user_id,
                    asset_id=a.id,
                    valuation_date=data['valuation_date'],
                    value_per_unit=data['value_per_unit'],
                )
                DB.session.add(v)
                DB.session.flush()
                _sync_asset_value_per_unit(AssetValuations, a)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                       Splits, WealthSnapshot, AssetValuations, user_id, data['valuation_date'])
                return json_response(_valuation_to_dict(v), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def update_valuation():
            try:
                data = UpdateValuationSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            v = AssetValuations.query.filter(
                AssetValuations.id == data['valuation_id'], AssetValuations.user_id == user_id).first()
            if not v:
                return json_response('Valuation not found', HttpCode.NOT_FOUND)
            a = Assets.query.filter_by(id=v.asset_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            if data['valuation_date'] != v.valuation_date and AssetValuations.query.filter_by(
                    asset_id=v.asset_id, valuation_date=data['valuation_date']).first():
                return json_response('Une valorisation existe déjà à cette date', HttpCode.CONFLICT)

            old_date = v.valuation_date
            try:
                v.valuation_date = data['valuation_date']
                v.value_per_unit = data['value_per_unit']
                DB.session.flush()
                _sync_asset_value_per_unit(AssetValuations, a)
                DB.session.commit()
                from_date = min(old_date, data['valuation_date'])
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                       Splits, WealthSnapshot, AssetValuations, user_id, from_date)
                return json_response(_valuation_to_dict(v), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/valuations", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def delete_valuation():
            try:
                data = DeleteValuationSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            v = AssetValuations.query.filter(
                AssetValuations.id == data['valuation_id'], AssetValuations.user_id == user_id).first()
            if not v:
                return json_response('Valuation not found', HttpCode.NOT_FOUND)
            a = Assets.query.filter_by(id=v.asset_id).first()
            valuation_date = v.valuation_date
            try:
                DB.session.delete(v)
                DB.session.flush()
                if a:
                    _sync_asset_value_per_unit(AssetValuations, a)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                       Splits, WealthSnapshot, AssetValuations, user_id, valuation_date)
                return json_response('Valuation deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        # ── Possessions ──────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/possessions", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def add_possession():
            try:
                data = AddPossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            dest_account = Accounts.query.filter(Accounts.id == data['account_id'], Accounts.user_id == user_id).first()
            if not dest_account:
                return json_response('Account not found', HttpCode.NOT_FOUND)
            if dest_account.account_type not in ('Assets', 'Equity'):
                return json_response("Le compte doit être de type 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            source_account_id = data.get('source_account_id')
            source_account = None
            if source_account_id:
                source_account = Accounts.query.filter(
                    Accounts.id == source_account_id, Accounts.user_id == user_id).first()
                if not source_account:
                    return json_response('Source account not found', HttpCode.NOT_FOUND)
                if source_account.account_type not in ('Current', 'Assets', 'Equity'):
                    return json_response(
                        "Le compte débité doit être de type 'Current', 'Assets' ou 'Equity'", HttpCode.BAD_REQUEST)

            commodity = Commodities.query.filter_by(id=a.commodity_id).first()
            if not commodity:
                return json_response('Commodity not found', HttpCode.NOT_FOUND)

            purchase_price_native = data['purchase_price']
            purchase_price = purchase_price_native
            if a.track_live_price:
                purchase_price, error = resolve_purchase_price(
                    a.symbol, commodity.short_name, purchase_price_native, data['purchase_date'], FxRates)
                if error:
                    return error

            settings = UserSettings.query.filter_by(user_id=user_id).first()
            default_currency = settings.currency if settings else 'EUR'
            manual_fx_rate = data.get('fx_rate')

            # Résolu (et persisté plus bas dans p.fx_rate) que le lot ait ou non un compte débité —
            # utile même sans mouvement d'argent réel : c'est ce taux qui reconvertira plus tard les
            # frais d'achat de CE lot spécifique lors d'une vente partielle (voir sell_possession),
            # sans redépendre d'une résolution automatique implicite a posteriori qui pourrait
            # tomber sur un taux historique différent si les données de change ont évolué entretemps.
            cost_asset_ccy = float(data['quantity']) * float(purchase_price)
            cost_default, resolved_fx_rate, error = convert_asset_to_default_currency(
                cost_asset_ccy, commodity.short_name, default_currency, manual_fx_rate,
                data['purchase_date'], FxRates)
            if error:
                return error
            if commodity.short_name == default_currency:
                resolved_fx_rate = None  # pas "1.0" : aucune conversion n'a de sens ici (même devise)

            dest_amount = source_amount = dest_fx_rate = None
            if source_account:
                # Les frais (toujours saisis en devise par défaut) s'ajoutent directement au coût
                # déjà ramené en devise par défaut ci-dessus : purchase_price reste lui un prix par
                # unité "propre", non pollué par le forfait de frais. Le total en devise par défaut
                # est ensuite reconverti automatiquement vers la devise réelle de chaque compte
                # impliqué (fiable même si la devise de l'actif est trop exotique pour avoir un
                # historique de change disponible).
                total_cost_default = cost_default + float(data['fees'])
                dest_amount, source_amount, dest_fx_rate, error = resolve_split_amounts(
                    Accounts, Commodities, dest_account, source_account, total_cost_default,
                    default_currency, data['purchase_date'], FxRates)
                if error:
                    return error

            try:
                tx = None
                source_split_id = dest_split_id = None
                if source_account:
                    tx = Transactions(
                        user_id=user_id,
                        currency_id=source_account.currency_id,
                        post_date=data['purchase_date'],
                        effective_date=data['purchase_date'],
                        description=f"Achat {a.symbol} x{format_qty(data['quantity'])}",
                        category_id=None,
                        is_cleared=True,
                    )
                    DB.session.add(tx)
                    DB.session.flush()
                    # Ids générés explicitement (pas de lookup par account_id à la modification —
                    # ambigu quand source_account == dest_account, cf. achat autofinancé par le CTO).
                    source_split_id, dest_split_id = uuid.uuid4(), uuid.uuid4()
                    DB.session.add(Splits(id=source_split_id, tx_id=tx.id, account_id=source_account.id, quantity=-source_amount, fx_rate=1.0))
                    DB.session.add(Splits(id=dest_split_id, tx_id=tx.id, account_id=dest_account.id, quantity=dest_amount, fx_rate=dest_fx_rate))
                    DB.session.flush()

                p = AssetPossession(
                    user_id=user_id,
                    asset_id=data['asset_id'],
                    account_id=data['account_id'],
                    source_account_id=source_account_id,
                    tx_id=tx.id if tx else None,
                    source_split_id=source_split_id,
                    dest_split_id=dest_split_id,
                    quantity=data['quantity'],
                    purchase_price=purchase_price,
                    purchase_price_native=purchase_price_native,
                    fees=data['fees'],
                    fx_rate=resolved_fx_rate,
                    purchase_date=data['purchase_date'],
                )
                DB.session.add(p)
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits,
                                       WealthSnapshot, AssetValuations, user_id, data['purchase_date'])
                return json_response(_possession_to_dict(p), HttpCode.CREATED)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def update_possession():
            try:
                data = UpdatePossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            p = AssetPossession.query.filter(
                AssetPossession.id == data['possession_id'],
                AssetPossession.user_id == user_id
            ).first()
            if not p:
                return json_response('Possession not found', HttpCode.NOT_FOUND)

            existing_disposals = AssetDisposal.query.filter_by(possession_id=p.id).all()
            sold_qty = sum(disp.quantity for disp in existing_disposals)
            if data['quantity'] < sold_qty:
                return json_response(
                    f"Impossible de réduire la quantité en dessous de {sold_qty} "
                    f"(déjà cédée via {len(existing_disposals)} vente(s))",
                    HttpCode.BAD_REQUEST)

            purchase_price_native = data['purchase_price']
            purchase_price = purchase_price_native
            a = Assets.query.filter_by(id=p.asset_id).first()
            commodity = Commodities.query.filter_by(id=a.commodity_id).first() if a else None
            if a and a.track_live_price:
                if not commodity:
                    return json_response('Commodity not found', HttpCode.NOT_FOUND)
                purchase_price, error = resolve_purchase_price(
                    a.symbol, commodity.short_name, purchase_price_native, data['purchase_date'], FxRates)
                if error:
                    return error

            settings = UserSettings.query.filter_by(user_id=user_id).first()
            default_currency = settings.currency if settings else 'EUR'
            manual_fx_rate = data.get('fx_rate')

            resolved_fx_rate = None
            dest_amount = source_amount = dest_fx_rate = None
            if commodity:
                cost_asset_ccy = float(data['quantity']) * float(purchase_price)
                cost_default, resolved_fx_rate, error = convert_asset_to_default_currency(
                    cost_asset_ccy, commodity.short_name, default_currency, manual_fx_rate,
                    data['purchase_date'], FxRates)
                if error:
                    return error
                if commodity.short_name == default_currency:
                    resolved_fx_rate = None
                if p.tx_id and p.source_account_id:
                    dest_account = Accounts.query.filter_by(id=p.account_id).first()
                    source_account = Accounts.query.filter_by(id=p.source_account_id).first()
                    total_cost_default = cost_default + float(data['fees'])
                    dest_amount, source_amount, dest_fx_rate, error = resolve_split_amounts(
                        Accounts, Commodities, dest_account, source_account, total_cost_default,
                        default_currency, data['purchase_date'], FxRates)
                    if error:
                        return error

            old_purchase_date = p.purchase_date.date() if p.purchase_date else None
            try:
                p.quantity = data['quantity']
                p.purchase_price = purchase_price
                p.purchase_price_native = purchase_price_native
                p.fees = data['fees']
                p.fx_rate = resolved_fx_rate
                p.purchase_date = data['purchase_date']

                if p.tx_id and dest_amount is not None:
                    tx = Transactions.query.filter_by(id=p.tx_id).first()
                    if tx:
                        tx.post_date = data['purchase_date']
                        tx.effective_date = data['purchase_date']
                        tx.description = f"Achat {a.symbol} x{format_qty(data['quantity'])}"
                    source_split = Splits.query.filter_by(id=p.source_split_id).first()
                    dest_split = Splits.query.filter_by(id=p.dest_split_id).first()
                    if source_split:
                        source_split.quantity = -source_amount
                    if dest_split:
                        dest_split.quantity = dest_amount
                        dest_split.fx_rate = dest_fx_rate

                DB.session.commit()
                if old_purchase_date != data['purchase_date']:
                    from_date = min(old_purchase_date, data['purchase_date']) if old_purchase_date else data['purchase_date']
                    _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                           Splits, WealthSnapshot, AssetValuations, user_id, from_date)
                return json_response(_possession_to_dict(p, existing_disposals), HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def delete_possession():
            try:
                data = DeletePossessionSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            p = AssetPossession.query.filter(
                AssetPossession.id == data['possession_id'],
                AssetPossession.user_id == user_id
            ).first()
            if not p:
                return json_response('Possession not found', HttpCode.NOT_FOUND)
            if AssetDisposal.query.filter_by(possession_id=p.id).first():
                return json_response('Possession is still used by one or more disposals (sales)', HttpCode.CONFLICT)
            purchase_date = p.purchase_date.date() if p.purchase_date else None
            tx_id = p.tx_id
            try:
                DB.session.delete(p)
                if tx_id:
                    tx = Transactions.query.filter_by(id=tx_id).first()
                    if tx:
                        DB.session.delete(tx)  # cascade supprime les Splits liés (splits.py: ondelete='CASCADE')
                DB.session.commit()
                if purchase_date:
                    _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions,
                                           Splits, WealthSnapshot, AssetValuations, user_id, purchase_date)
                return json_response('Possession deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions/sell", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def sell_possession():
            try:
                data = SellPossessionSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            try:
                a, position_account, disposals = _execute_sale(
                    DB, Assets, AssetPossession, AssetDisposal, Commodities, Accounts, Transactions, Splits,
                    UserSettings, FxRates, user_id=user_id, asset_id=data['asset_id'], account_id=data['account_id'],
                    quantity=data['quantity'], sale_price_native=data['sale_price'], sale_date=data['sale_date'],
                    fees=data['fees'], dest_account_id=data.get('dest_account_id'), manual_fx_rate=data.get('fx_rate'),
                    sale_id=uuid.uuid4(),
                )
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                                       Transactions, Splits, WealthSnapshot, AssetValuations, user_id, data['sale_date'])
                return json_response({
                    'asset_id': str(a.id),
                    'account_id': str(position_account.id),
                    'quantity_sold': float(data['quantity']),
                    'lots_touched': len(disposals),
                    'disposals': [{
                        'id': str(d.id), 'possession_id': str(d.possession_id), 'quantity': float(d.quantity),
                        'realized_gain': float(d.realized_gain) if d.realized_gain is not None else None,
                    } for d in disposals],
                }, HttpCode.CREATED)
            except _OperationError as e:
                DB.session.rollback()
                return e.response if e.response is not None else json_response(e.message, e.code)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions/sell", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def update_sale():
            """Modifie UNE vente, c'est-à-dire tous les AssetDisposal partageant le même sale_id (une
            vente FIFO peut avoir touché plusieurs lots à la fois) — pas une ligne précise. L'actif et
            le compte de la position ne sont pas éditables (déduits des cessions existantes, comme
            account_id est figé sur update_possession) ; supprime l'ancienne vente puis en recrée une
            nouvelle avec les nouvelles valeurs via _execute_sale, dans la même transaction DB pour
            garantir qu'un échec de validation ne laisse pas l'ancienne vente à moitié supprimée."""
            try:
                data = UpdateSaleSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()

            existing = AssetDisposal.query.filter_by(sale_id=data['sale_id'], user_id=user_id).all()
            if not existing:
                return json_response('Sale not found', HttpCode.NOT_FOUND)
            if any(d.operation_id for d in existing):
                return json_response(
                    "Impossible de modifier une cession créée par une opération sur titre", HttpCode.BAD_REQUEST)

            first_possession = AssetPossession.query.filter_by(id=existing[0].possession_id).first()
            if not first_possession:
                return json_response('Possession not found', HttpCode.NOT_FOUND)
            asset_id, account_id = first_possession.asset_id, first_possession.account_id
            old_min_date = min((d.sale_date.date() if hasattr(d.sale_date, 'date') else d.sale_date) for d in existing)
            old_tx_ids = {d.tx_id for d in existing if d.tx_id}

            try:
                for d in existing:
                    DB.session.delete(d)
                DB.session.flush()
                for tx_id in old_tx_ids:
                    tx = Transactions.query.filter_by(id=tx_id).first()
                    if tx:
                        DB.session.delete(tx)  # cascade supprime les Splits liés (splits.py: ondelete='CASCADE')
                DB.session.flush()

                a, position_account, disposals = _execute_sale(
                    DB, Assets, AssetPossession, AssetDisposal, Commodities, Accounts, Transactions, Splits,
                    UserSettings, FxRates, user_id=user_id, asset_id=asset_id, account_id=account_id,
                    quantity=data['quantity'], sale_price_native=data['sale_price'], sale_date=data['sale_date'],
                    fees=data['fees'], dest_account_id=data.get('dest_account_id'), manual_fx_rate=data.get('fx_rate'),
                    sale_id=data['sale_id'],
                )
                DB.session.commit()
                refresh_from = min(old_min_date, data['sale_date'])
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                                       Transactions, Splits, WealthSnapshot, AssetValuations, user_id, refresh_from)
                return json_response({
                    'asset_id': str(a.id),
                    'account_id': str(position_account.id),
                    'quantity_sold': float(data['quantity']),
                    'lots_touched': len(disposals),
                    'disposals': [{
                        'id': str(d.id), 'possession_id': str(d.possession_id), 'quantity': float(d.quantity),
                        'realized_gain': float(d.realized_gain) if d.realized_gain is not None else None,
                    } for d in disposals],
                }, HttpCode.OK)
            except _OperationError as e:
                DB.session.rollback()
                return e.response if e.response is not None else json_response(e.message, e.code)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/possessions/sell", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def delete_sale():
            """Supprime UNE vente entière (tous les AssetDisposal partageant le même sale_id), et la
            Transaction/Splits partagés s'il y en a — restaure la quantité sur le(s) lot(s) d'origine
            comme delete_possession restaure une position achetée."""
            try:
                data = DeleteSaleSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()

            existing = AssetDisposal.query.filter_by(sale_id=data['sale_id'], user_id=user_id).all()
            if not existing:
                return json_response('Sale not found', HttpCode.NOT_FOUND)
            if any(d.operation_id for d in existing):
                return json_response(
                    "Impossible de supprimer une cession créée par une opération sur titre", HttpCode.BAD_REQUEST)

            sale_date = min((d.sale_date.date() if hasattr(d.sale_date, 'date') else d.sale_date) for d in existing)
            tx_ids = {d.tx_id for d in existing if d.tx_id}
            try:
                for d in existing:
                    DB.session.delete(d)
                for tx_id in tx_ids:
                    tx = Transactions.query.filter_by(id=tx_id).first()
                    if tx:
                        DB.session.delete(tx)  # cascade supprime les Splits liés (splits.py: ondelete='CASCADE')
                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                                       Transactions, Splits, WealthSnapshot, AssetValuations, user_id, sale_date)
                return json_response('Sale deleted', HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)

        # ── Opérations sur titre (split, fusion, scission) ──────────────────

        @app.route(f"{ROUTE_PATH}/operations", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def get_asset_operations():
            try:
                data = GetAssetOperationsSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()
            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)
            operations = AssetOperations.query.filter_by(user_id=user_id, asset_id=a.id) \
                .order_by(AssetOperations.operation_date.desc()).all()
            return json_response([_operation_to_dict(o) for o in operations], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/operations", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, ASSETS_PERM)
        def create_asset_operation():
            """Applique une opération sur titre décidée par l'émetteur à TOUS les lots de l'actif
            source, tous comptes confondus. Les 3 types partagent un principe commun : ne jamais
            changer un euro déjà réalisé dans le passé ni la valeur totale actuelle, seulement
            re-dénominer le "prix par part" — voir le détail par branche ci-dessous et le plan associé.
            Ne touche jamais Transactions/Splits (grand livre) : aucune opération ici ne bouge de cash."""
            try:
                data = CreateAssetOperationSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)
            user_id = get_jwt_identity()

            a = Assets.query.filter(Assets.id == data['asset_id'], Assets.user_id == user_id).first()
            if not a:
                return json_response('Asset not found', HttpCode.NOT_FOUND)

            op_type = data['operation_type']
            target = target_commodity = None
            if op_type in ('merger', 'spinoff'):
                target_id = data.get('target_asset_id')
                if not target_id:
                    return json_response(
                        "target_asset_id est obligatoire pour une fusion ou une scission", HttpCode.BAD_REQUEST)
                if target_id == data['asset_id']:
                    return json_response("L'actif cible doit être différent de l'actif source", HttpCode.BAD_REQUEST)
                target = Assets.query.filter(Assets.id == target_id, Assets.user_id == user_id).first()
                if not target:
                    return json_response('Target asset not found', HttpCode.NOT_FOUND)
                target_commodity = Commodities.query.filter_by(id=target.commodity_id).first()
                if not target_commodity:
                    return json_response('Target commodity not found', HttpCode.NOT_FOUND)
            if op_type == 'spinoff' and data.get('cost_allocation_pct') is None:
                return json_response("cost_allocation_pct est obligatoire pour une scission", HttpCode.BAD_REQUEST)

            settings = UserSettings.query.filter_by(user_id=user_id).first()
            default_currency = settings.currency if settings else 'EUR'
            ratio = float(data['ratio_to']) / float(data['ratio_from'])
            operation_date = data['operation_date']

            # Seuls les lots déjà détenus au moment de l'opération sont concernés — un lot acheté
            # après (purchase_date > operation_date) reflète déjà la structure de titre post-opération
            # (ex: rachat après un split, déjà au nouveau ratio) et ne doit ni être rescalé/clôturé/
            # scindé, ni recevoir de part de l'actif cible. purchase_date le jour même de l'opération
            # est traité comme "déjà détenu" (une seule date, pas d'heure, saisie côté utilisateur).
            lots = [
                p for p in AssetPossession.query.filter_by(user_id=user_id, asset_id=a.id).all()
                if not p.purchase_date
                or (p.purchase_date.date() if hasattr(p.purchase_date, 'date') else p.purchase_date) <= operation_date
            ]
            lot_ids = [p.id for p in lots]
            disposals_by_lot = {}
            if lot_ids:
                for d in AssetDisposal.query.filter(AssetDisposal.possession_id.in_(lot_ids)).all():
                    disposals_by_lot.setdefault(d.possession_id, []).append(d)

            def resolve_target_purchase_price(cost_in_default_ccy, new_qty):
                """Convertit un coût en devise par défaut vers la devise native de l'actif cible, au
                taux historique de operation_date (même convention que AssetPossession.fx_rate
                ailleurs dans ce fichier : None si devises identiques). Retourne (purchase_price, fx_rate)."""
                if target_commodity.short_name == default_currency:
                    return cost_in_default_ccy / new_qty, None
                rate = get_fx_rate(target_commodity.short_name, default_currency, FxRates, on_date=operation_date)
                if rate is None:
                    raise _OperationError(
                        f"Taux de change historique {target_commodity.short_name} → {default_currency} "
                        f"indisponible pour la date de l'opération")
                return (cost_in_default_ccy / rate) / new_qty, rate

            try:
                operation = AssetOperations(
                    user_id=user_id, asset_id=a.id, operation_type=op_type, operation_date=operation_date,
                    ratio_from=data['ratio_from'], ratio_to=data['ratio_to'],
                    target_asset_id=target.id if target else None,
                    cost_allocation_pct=data.get('cost_allocation_pct'), note=data.get('note'),
                )
                DB.session.add(operation)
                DB.session.flush()

                if op_type == 'split':
                    # Rescale EN PLACE, sur tous les lots (y compris déjà partiellement/totalement
                    # vendus, pour rester dimensionnellement cohérent avec les cessions passées) :
                    # quantité × ratio, prix par unité ÷ ratio — la valeur totale et le gain réalisé
                    # de chaque vente passée restent mathématiquement invariants sous cette transfo.
                    for p in lots:
                        p.quantity = float(p.quantity) * ratio
                        if p.purchase_price is not None:
                            p.purchase_price = float(p.purchase_price) / ratio
                        if p.purchase_price_native is not None:
                            p.purchase_price_native = float(p.purchase_price_native) / ratio
                        for d in disposals_by_lot.get(p.id, []):
                            d.quantity = float(d.quantity) * ratio
                            if d.sale_price is not None:
                                d.sale_price = float(d.sale_price) / ratio
                            if d.sale_price_native is not None:
                                d.sale_price_native = float(d.sale_price_native) / ratio
                            # realized_gain inchangé : invariant sous cette transformation.
                    a.value_per_unit = float(a.value_per_unit or 0) / ratio
                    for v in AssetValuations.query.filter(
                            AssetValuations.asset_id == a.id, AssetValuations.valuation_date < operation_date).all():
                        v.value_per_unit = float(v.value_per_unit) / ratio

                elif op_type == 'merger':
                    # L'actif source disparaît : chaque lot restant est clôturé (cession synthétique,
                    # gain nul — rollover fiscalement neutre, pas de composante cash en v1) et son coût
                    # de revient intégral roule vers un nouveau lot sur l'actif cible, même compte,
                    # même date d'achat d'origine (durée de détention conservée).
                    for p in lots:
                        disposed = sum(float(d.quantity) for d in disposals_by_lot.get(p.id, []))
                        remaining = float(p.quantity) - disposed
                        if remaining <= 1e-9:
                            continue
                        fx_for_cost = float(p.fx_rate) if p.fx_rate is not None else 1.0
                        basis = cost_basis_per_unit(p.purchase_price, p.fees, p.quantity, fx_for_cost)
                        cost_remaining = basis * remaining if basis is not None else None

                        holding_period_days = None
                        if p.purchase_date:
                            purchase_date_only = p.purchase_date.date() if hasattr(p.purchase_date, 'date') else p.purchase_date
                            holding_period_days = (operation_date - purchase_date_only).days

                        DB.session.add(AssetDisposal(
                            user_id=user_id, possession_id=p.id, quantity=remaining,
                            sale_price=p.purchase_price, sale_price_native=p.purchase_price_native,
                            fees=0, fx_rate=p.fx_rate, sale_date=operation_date, dest_account_id=None,
                            tx_id=None, realized_gain=(0 if cost_remaining is not None else None),
                            holding_period_days=holding_period_days, operation_id=operation.id,
                        ))

                        new_qty = remaining * ratio
                        new_purchase_price = new_fx_rate = None
                        if cost_remaining is not None:
                            new_purchase_price, new_fx_rate = resolve_target_purchase_price(cost_remaining, new_qty)

                        DB.session.add(AssetPossession(
                            user_id=user_id, asset_id=target.id, account_id=p.account_id,
                            source_account_id=None, tx_id=None, quantity=new_qty,
                            purchase_price=new_purchase_price, purchase_price_native=new_purchase_price,
                            fees=0, fx_rate=new_fx_rate, purchase_date=p.purchase_date,
                            operation_id=operation.id,
                        ))

                else:  # spinoff
                    # L'actif source continue d'exister : quantité inchangée, mais son prix de revient
                    # est réduit de la part transférée vers l'actif cible (pct saisi par l'utilisateur —
                    # ne peut pas être déduit automatiquement, dépend de valeurs de marché externes).
                    pct = float(data['cost_allocation_pct'])
                    for p in lots:
                        disposed = sum(float(d.quantity) for d in disposals_by_lot.get(p.id, []))
                        remaining = float(p.quantity) - disposed
                        if remaining <= 1e-9:
                            continue
                        fx_for_cost = float(p.fx_rate) if p.fx_rate is not None else 1.0
                        basis = cost_basis_per_unit(p.purchase_price, p.fees, p.quantity, fx_for_cost)
                        new_qty = remaining * ratio

                        if basis is None:
                            # Coût inconnu sur le lot source : rien à réallouer, on octroie juste les
                            # nouvelles parts avec un coût inconnu, sans toucher au lot source.
                            DB.session.add(AssetPossession(
                                user_id=user_id, asset_id=target.id, account_id=p.account_id,
                                source_account_id=None, tx_id=None, quantity=new_qty,
                                purchase_price=None, purchase_price_native=None, fees=0, fx_rate=None,
                                purchase_date=p.purchase_date, operation_id=operation.id,
                            ))
                            continue

                        total_cost = basis * remaining
                        transferred_cost = total_cost * (pct / 100)
                        kept_cost = total_cost - transferred_cost

                        # Lot source modifié en place (quantité inchangée) : le prix de revient est
                        # recalculé pour refléter kept_cost, frais remis à 0 (déjà absorbés dedans).
                        p.purchase_price = (kept_cost / remaining) / fx_for_cost
                        p.purchase_price_native = p.purchase_price
                        p.fees = 0

                        new_purchase_price, new_fx_rate = resolve_target_purchase_price(transferred_cost, new_qty)
                        DB.session.add(AssetPossession(
                            user_id=user_id, asset_id=target.id, account_id=p.account_id,
                            source_account_id=None, tx_id=None, quantity=new_qty,
                            purchase_price=new_purchase_price, purchase_price_native=new_purchase_price,
                            fees=0, fx_rate=new_fx_rate, purchase_date=p.purchase_date,
                            operation_id=operation.id,
                        ))

                DB.session.commit()
                _force_wealth_refresh(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                                       Transactions, Splits, WealthSnapshot, AssetValuations, user_id, operation_date)
                return json_response(_operation_to_dict(operation), HttpCode.CREATED)
            except _OperationError as e:
                DB.session.rollback()
                return json_response(e.message, e.code)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
