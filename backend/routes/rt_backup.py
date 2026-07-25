import base64
import hashlib
import io
import os
import uuid
import zipfile
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from flask import request, Response
import json as json_lib
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH
from backend.utils.api_responses import json_response
from backend.version import APP_VERSION

BACKUP_FORMAT_VERSION = 1


# ── Sérialisation (export) ──────────────────────────────────────────────────

def _u(v):
    return str(v) if v is not None else None


def _n(v):
    return float(v) if v is not None else None


def _dt(v):
    return v.isoformat() if v is not None else None


def _parse_dt(v, fallback=None):
    if not v:
        return fallback
    return datetime.fromisoformat(v)


def _parse_date(v):
    if not v:
        return None
    return date.fromisoformat(v[:10])


def _dec(v):
    """Convertit une valeur JSON (float/str/None) en Decimal pour comparaison exacte avec les
    colonnes Numeric — évite les faux négatifs/positifs de dédoublonnage dus à l'arrondi float."""
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return None


def _doc_zip_path(doc_id, original_filename):
    """Nom de fichier sûr dans l'archive : basename seul (jamais de séparateur de chemin fourni
    par l'utilisateur) préfixé par l'id pour garantir l'unicité même si deux justificatifs
    partagent le même nom d'origine."""
    safe_name = os.path.basename(original_filename or 'document').strip() or 'document'
    return f"documents/{doc_id}_{safe_name}"


def export_user_data(user_id, DB, Commodities, Accounts, Categories, Tags, Budgets, BudgetAccounts,
                      BudgetCategories, BudgetTags, Subscriptions, Assets, AssetPossession, AssetDisposal,
                      AssetValuations, Transactions, Splits, TagsOnSplits, UserSettings,
                      TransactionDocuments):
    commodities = Commodities.query.filter_by(user_id=user_id).all()
    accounts = Accounts.query.filter_by(user_id=user_id).all()
    categories = Categories.query.filter_by(user_id=user_id).all()
    tags = Tags.query.filter_by(user_id=user_id).all()
    budgets = Budgets.query.filter_by(user_id=user_id).all()
    budget_ids = [b.id for b in budgets]
    budget_accounts = BudgetAccounts.query.filter(BudgetAccounts.budget_id.in_(budget_ids)).all() if budget_ids else []
    budget_categories = BudgetCategories.query.filter(BudgetCategories.budget_id.in_(budget_ids)).all() if budget_ids else []
    budget_tags = BudgetTags.query.filter(BudgetTags.budget_id.in_(budget_ids)).all() if budget_ids else []
    subscriptions = Subscriptions.query.filter_by(user_id=user_id).all()
    assets = Assets.query.filter_by(user_id=user_id).all()
    asset_possessions = AssetPossession.query.filter_by(user_id=user_id).all()
    asset_disposals = AssetDisposal.query.filter_by(user_id=user_id).all()
    asset_valuations = AssetValuations.query.filter_by(user_id=user_id).all()
    transactions = Transactions.query.filter_by(user_id=user_id).all()
    tx_ids = [t.id for t in transactions]
    splits = Splits.query.filter(Splits.tx_id.in_(tx_ids)).all() if tx_ids else []
    split_ids = [s.id for s in splits]
    tags_on_split = TagsOnSplits.query.filter(TagsOnSplits.split_id.in_(split_ids)).all() if split_ids else []
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    # Seuls les justificatifs confirmés (rattachés à une transaction) sont de vraies données
    # utilisateur — 'pending' est un état transitoire de relecture OCR en cours, jamais persistant.
    documents = TransactionDocuments.query.filter_by(user_id=user_id, status='confirmed').all()

    data = {
        'backup_format_version': BACKUP_FORMAT_VERSION,
        'app_version': APP_VERSION,
        'exported_at': _dt(datetime.now()),
        'commodities': [{
            'id': _u(c.id), 'name': c.name, 'short_name': c.short_name, 'type': c.type,
            'fraction': c.fraction, 'description': c.description, 'track_live_rate': c.track_live_rate,
        } for c in commodities],
        'accounts': [{
            'id': _u(a.id), 'name': a.name, 'parent_id': _u(a.parent_id), 'account_type': a.account_type,
            'account_subtype': a.account_subtype, 'currency_id': _u(a.currency_id), 'description': a.description,
            'is_virtual': a.is_virtual, 'is_hidden': a.is_hidden, 'code': a.code,
        } for a in accounts],
        'categories': [{
            'id': _u(c.id), 'name': c.name, 'description': c.description,
        } for c in categories],
        'tags': [{
            'id': _u(t.id), 'name': t.name, 'color': t.color,
        } for t in tags],
        'budgets': [{
            'id': _u(b.id), 'name': b.name, 'amount_allocated': _n(b.amount_allocated),
            'start_date': _dt(b.start_date), 'end_date': _dt(b.end_date),
        } for b in budgets],
        'budget_accounts': [{'budget_id': _u(x.budget_id), 'account_id': _u(x.account_id)} for x in budget_accounts],
        'budget_categories': [{'budget_id': _u(x.budget_id), 'category_id': _u(x.category_id)} for x in budget_categories],
        'budget_tags': [{'budget_id': _u(x.budget_id), 'tag_id': _u(x.tag_id)} for x in budget_tags],
        'subscriptions': [{
            'id': _u(s.id), 'name': s.name, 'schedule_type': s.schedule_type, 'day_of_month': s.day_of_month,
            'month_of_year': s.month_of_year, 'weekdays': s.weekdays, 'amount': _n(s.amount),
            'from_account_id': _u(s.from_account_id), 'to_account_id': _u(s.to_account_id),
            'category_id': _u(s.category_id), 'is_forecast_only': s.is_forecast_only,
        } for s in subscriptions],
        'assets': [{
            'id': _u(a.id), 'symbol': a.symbol, 'name': a.name, 'asset_type': a.asset_type, 'sector': a.sector,
            'commodity_id': _u(a.commodity_id), 'value_per_unit': _n(a.value_per_unit),
            'track_live_price': a.track_live_price,
        } for a in assets],
        'asset_possessions': [{
            'id': _u(p.id), 'asset_id': _u(p.asset_id), 'account_id': _u(p.account_id),
            'source_account_id': _u(p.source_account_id), 'quantity': p.quantity,
            'purchase_price': _n(p.purchase_price), 'purchase_price_native': _n(p.purchase_price_native),
            'purchase_date': _dt(p.purchase_date),
        } for p in asset_possessions],
        # tx_id/source_split_id/dest_split_id volontairement absents, même raison que pour
        # asset_possessions (voir commentaire dans import_user_data) — la donnée fiscale/patrimoniale
        # (quantité, prix, date, plus-value) est préservée intégralement sans reconstituer les splits.
        'asset_disposals': [{
            'id': _u(d.id), 'possession_id': _u(d.possession_id), 'quantity': d.quantity,
            'sale_price': _n(d.sale_price), 'sale_price_native': _n(d.sale_price_native),
            'sale_date': _dt(d.sale_date), 'dest_account_id': _u(d.dest_account_id),
            'realized_gain': _n(d.realized_gain), 'holding_period_days': d.holding_period_days,
        } for d in asset_disposals],
        'asset_valuations': [{
            'id': _u(v.id), 'asset_id': _u(v.asset_id), 'valuation_date': _dt(v.valuation_date),
            'value_per_unit': _n(v.value_per_unit),
        } for v in asset_valuations],
        'transactions': [{
            'id': _u(t.id), 'currency_id': _u(t.currency_id), 'post_date': _dt(t.post_date),
            'effective_date': _dt(t.effective_date), 'description': t.description,
            'category_id': _u(t.category_id), 'is_cleared': t.is_cleared,
        } for t in transactions],
        'splits': [{
            'id': _u(s.id), 'tx_id': _u(s.tx_id), 'account_id': _u(s.account_id), 'quantity': _n(s.quantity),
            'is_reconciled': s.is_reconciled, 'description': s.description, 'fx_rate': _n(s.fx_rate),
        } for s in splits],
        'tags_on_split': [{'split_id': _u(x.split_id), 'tag_id': _u(x.tag_id)} for x in tags_on_split],
        # Les binaires ne sont plus embarqués en base64 ici : ils sont stockés à part dans
        # l'archive zip (voir doc_files ci-dessous) et référencés par chemin, ce qui évite le
        # surcoût de ~33% de base64 et permet de parcourir/extraire les fichiers directement.
        'transaction_documents': [{
            'id': _u(d.id), 'tx_id': _u(d.tx_id), 'original_filename': d.original_filename,
            'mime_type': d.mime_type, 'uploaded_at': _dt(d.uploaded_at),
            'file_path': _doc_zip_path(d.id, d.original_filename),
        } for d in documents],
        'user_settings': ({
            'currency': settings.currency, 'date_format': settings.date_format,
            'market_score_weights': settings.market_score_weights,
            'market_score_thresholds': settings.market_score_thresholds,
        } if settings else None),
    }
    doc_files = [{'path': _doc_zip_path(d.id, d.original_filename), 'bytes': d.file_data} for d in documents]

    return data, doc_files


# ── Import (matching par clé naturelle, dans l'ordre de dépendance) ─────────

def _resolve(cache, key, finder, creator, DB):
    """cache: dict clé naturelle -> id local. Retourne (id_local, created:bool)."""
    if key in cache:
        return cache[key], False
    existing = finder()
    if existing:
        cache[key] = existing.id
        return existing.id, False
    obj = creator()
    DB.session.add(obj)
    DB.session.flush()
    cache[key] = obj.id
    return obj.id, True


def import_user_data(user_id, payload, DB, Commodities, Accounts, Categories, Tags, Budgets, BudgetAccounts,
                      BudgetCategories, BudgetTags, Subscriptions, Assets, AssetPossession, AssetDisposal,
                      AssetValuations, Transactions, Splits, TagsOnSplits, UserSettings,
                      TransactionDocuments, apply_settings=False):
    report = {}

    def bump(entity, created):
        r = report.setdefault(entity, {'created': 0, 'matched': 0})
        r['created' if created else 'matched'] += 1

    # id export -> id local, un dict par type d'entité (les UUID d'export ne sont pas globalement
    # uniques entre types, ex. rien ne garantit qu'un id de compte ne collisionne pas avec un id de
    # catégorie dans deux exports différents concaténés à la main).
    map_commodity, map_account, map_category, map_tag = {}, {}, {}, {}
    map_budget, map_subscription, map_asset, map_tx = {}, {}, {}, {}
    map_possession = {}

    # ── Commodities ──────────────────────────────────────────────────────────
    cache_commodity = {c.short_name.strip().upper(): c
                        for c in Commodities.query.filter_by(user_id=user_id).all()}
    for row in payload.get('commodities', []):
        key = row['short_name'].strip().upper()
        existing = cache_commodity.get(key)
        if existing:
            map_commodity[row['id']] = existing.id
            bump('commodities', False)
        else:
            obj = Commodities(user_id=user_id, name=row['name'], short_name=row['short_name'],
                              type=row.get('type', 'Currency'), fraction=row.get('fraction', 2),
                              description=row.get('description'), track_live_rate=row.get('track_live_rate', False))
            DB.session.add(obj)
            DB.session.flush()
            cache_commodity[key] = obj
            map_commodity[row['id']] = obj.id
            bump('commodities', True)

    # ── Accounts (ordre topologique sur parent_id) ──────────────────────────
    cache_account = {a.name: a for a in Accounts.query.filter_by(user_id=user_id).all()}
    remaining = list(payload.get('accounts', []))
    while remaining:
        progressed = False
        still_remaining = []
        for row in remaining:
            parent_export_id = row.get('parent_id')
            if parent_export_id and parent_export_id not in map_account:
                still_remaining.append(row)
                continue
            existing = cache_account.get(row['name'])
            if existing:
                map_account[row['id']] = existing.id
                bump('accounts', False)
            else:
                currency_local = map_commodity.get(row.get('currency_id'))
                if not currency_local:
                    still_remaining.append(row)
                    continue
                obj = Accounts(
                    user_id=user_id, name=row['name'],
                    parent_id=map_account.get(parent_export_id) if parent_export_id else None,
                    account_type=row.get('account_type', 'Current'), account_subtype=row.get('account_subtype'),
                    currency_id=currency_local, description=row.get('description'),
                    is_virtual=row.get('is_virtual', False), is_hidden=row.get('is_hidden', False),
                    code=row.get('code'))
                DB.session.add(obj)
                DB.session.flush()
                cache_account[row['name']] = obj
                map_account[row['id']] = obj.id
                bump('accounts', True)
            progressed = True
        if not progressed:
            # Référence manquante dans le fichier (parent ou devise absents de l'export) : on
            # abandonne ces lignes plutôt que de boucler indéfiniment.
            for row in still_remaining:
                report.setdefault('errors', []).append(f"Compte '{row.get('name')}' ignoré (référence introuvable)")
            break
        remaining = still_remaining

    # ── Categories ───────────────────────────────────────────────────────────
    cache_category = {c.name: c for c in Categories.query.filter_by(user_id=user_id).all()}
    for row in payload.get('categories', []):
        existing = cache_category.get(row['name'])
        if existing:
            map_category[row['id']] = existing.id
            bump('categories', False)
        else:
            obj = Categories(user_id=user_id, name=row['name'], description=row.get('description'))
            DB.session.add(obj)
            DB.session.flush()
            cache_category[row['name']] = obj
            map_category[row['id']] = obj.id
            bump('categories', True)

    # ── Tags ─────────────────────────────────────────────────────────────────
    cache_tag = {t.name: t for t in Tags.query.filter_by(user_id=user_id).all()}
    for row in payload.get('tags', []):
        existing = cache_tag.get(row['name'])
        if existing:
            map_tag[row['id']] = existing.id
            bump('tags', False)
        else:
            obj = Tags(user_id=user_id, name=row['name'], color=row.get('color', 'green'))
            DB.session.add(obj)
            DB.session.flush()
            cache_tag[row['name']] = obj
            map_tag[row['id']] = obj.id
            bump('tags', True)

    # ── Budgets (clé : nom + dates) ──────────────────────────────────────────
    existing_budgets = Budgets.query.filter_by(user_id=user_id).all()
    cache_budget = {(b.name, b.start_date.date(), b.end_date.date()): b for b in existing_budgets}
    for row in payload.get('budgets', []):
        start = _parse_dt(row.get('start_date'))
        end = _parse_dt(row.get('end_date'))
        key = (row['name'], start.date() if start else None, end.date() if end else None)
        existing = cache_budget.get(key)
        if existing:
            map_budget[row['id']] = existing.id
            bump('budgets', False)
        else:
            obj = Budgets(user_id=user_id, name=row['name'],
                          amount_allocated=row.get('amount_allocated', 0),
                          start_date=start, end_date=end)
            DB.session.add(obj)
            DB.session.flush()
            cache_budget[key] = obj
            map_budget[row['id']] = obj.id
            bump('budgets', True)

    for row in payload.get('budget_accounts', []):
        b_id, a_id = map_budget.get(row['budget_id']), map_account.get(row['account_id'])
        if not (b_id and a_id):
            continue
        if not BudgetAccounts.query.filter_by(budget_id=b_id, account_id=a_id).first():
            DB.session.add(BudgetAccounts(budget_id=b_id, account_id=a_id))
            bump('budget_accounts', True)
        else:
            bump('budget_accounts', False)

    for row in payload.get('budget_categories', []):
        b_id, c_id = map_budget.get(row['budget_id']), map_category.get(row['category_id'])
        if not (b_id and c_id):
            continue
        if not BudgetCategories.query.filter_by(budget_id=b_id, category_id=c_id).first():
            DB.session.add(BudgetCategories(budget_id=b_id, category_id=c_id))
            bump('budget_categories', True)
        else:
            bump('budget_categories', False)

    for row in payload.get('budget_tags', []):
        b_id, t_id = map_budget.get(row['budget_id']), map_tag.get(row['tag_id'])
        if not (b_id and t_id):
            continue
        if not BudgetTags.query.filter_by(budget_id=b_id, tag_id=t_id).first():
            DB.session.add(BudgetTags(budget_id=b_id, tag_id=t_id))
            bump('budget_tags', True)
        else:
            bump('budget_tags', False)
    DB.session.flush()

    # ── Subscriptions (clé : nom) ────────────────────────────────────────────
    cache_subscription = {s.name: s for s in Subscriptions.query.filter_by(user_id=user_id).all()}
    for row in payload.get('subscriptions', []):
        existing = cache_subscription.get(row['name'])
        if existing:
            map_subscription[row['id']] = existing.id
            bump('subscriptions', False)
        else:
            from_acc = map_account.get(row.get('from_account_id'))
            to_acc = map_account.get(row.get('to_account_id'))
            if not (from_acc and to_acc):
                report.setdefault('errors', []).append(f"Abonnement '{row.get('name')}' ignoré (compte introuvable)")
                continue
            obj = Subscriptions(
                user_id=user_id, name=row['name'], schedule_type=row.get('schedule_type', 'monthly'),
                day_of_month=row.get('day_of_month'), month_of_year=row.get('month_of_year'),
                weekdays=row.get('weekdays'), amount=row.get('amount', 0),
                from_account_id=from_acc, to_account_id=to_acc,
                category_id=map_category.get(row.get('category_id')),
                is_forecast_only=row.get('is_forecast_only', False))
            DB.session.add(obj)
            DB.session.flush()
            cache_subscription[row['name']] = obj
            map_subscription[row['id']] = obj.id
            bump('subscriptions', True)

    # ── Assets (clé : nom + type + devise) ───────────────────────────────────
    existing_assets = Assets.query.filter_by(user_id=user_id).all()
    cache_asset = {(a.name, a.asset_type, a.commodity_id): a for a in existing_assets}
    for row in payload.get('assets', []):
        commodity_local = map_commodity.get(row.get('commodity_id'))
        key = (row['name'], row['asset_type'], commodity_local)
        existing = cache_asset.get(key)
        if existing:
            map_asset[row['id']] = existing.id
            bump('assets', False)
        else:
            if not commodity_local:
                report.setdefault('errors', []).append(f"Actif '{row.get('name')}' ignoré (devise introuvable)")
                continue
            obj = Assets(user_id=user_id, symbol=row['symbol'], name=row['name'], asset_type=row['asset_type'],
                        sector=row.get('sector'), commodity_id=commodity_local,
                        value_per_unit=row.get('value_per_unit', 0),
                        track_live_price=row.get('track_live_price', False))
            DB.session.add(obj)
            DB.session.flush()
            cache_asset[key] = obj
            map_asset[row['id']] = obj.id
            bump('assets', True)

    # ── AssetPossession (clé heuristique : actif + compte + date + qté + prix) ─
    # Les liens tx_id/source_split_id/dest_split_id (traçabilité vers la transaction d'origine) ne
    # sont pas ré-établis à l'import : reconstituer le bon split source de façon fiable serait
    # disproportionné pour une sauvegarde, la donnée patrimoniale elle-même (quantité, prix, date)
    # est préservée intégralement.
    existing_possessions = AssetPossession.query.filter_by(user_id=user_id).all()
    cache_possession = {
        (p.asset_id, p.account_id, p.purchase_date, p.quantity, p.purchase_price): p.id
        for p in existing_possessions
    }
    for row in payload.get('asset_possessions', []):
        asset_local = map_asset.get(row.get('asset_id'))
        account_local = map_account.get(row.get('account_id'))
        if not (asset_local and account_local):
            report.setdefault('errors', []).append("Possession d'actif ignorée (référence introuvable)")
            continue
        purchase_date = _parse_dt(row.get('purchase_date'))
        key = (asset_local, account_local, purchase_date, row.get('quantity'), _dec(row.get('purchase_price')))
        existing_id = cache_possession.get(key)
        if existing_id:
            map_possession[row['id']] = existing_id
            bump('asset_possessions', False)
        else:
            obj = AssetPossession(
                user_id=user_id, asset_id=asset_local, account_id=account_local,
                source_account_id=map_account.get(row.get('source_account_id')),
                quantity=row.get('quantity', 0), purchase_price=row.get('purchase_price'),
                purchase_price_native=row.get('purchase_price_native'), purchase_date=purchase_date)
            DB.session.add(obj)
            DB.session.flush()
            cache_possession[key] = obj.id
            map_possession[row['id']] = obj.id
            bump('asset_possessions', True)

    # ── AssetValuations (clé : actif + date) ─────────────────────────────────
    existing_valuations = AssetValuations.query.filter_by(user_id=user_id).all()
    cache_valuation = {(v.asset_id, v.valuation_date) for v in existing_valuations}
    for row in payload.get('asset_valuations', []):
        asset_local = map_asset.get(row.get('asset_id'))
        if not asset_local:
            continue
        v_date = _parse_date(row.get('valuation_date'))
        key = (asset_local, v_date)
        if key in cache_valuation:
            bump('asset_valuations', False)
        else:
            DB.session.add(AssetValuations(user_id=user_id, asset_id=asset_local, valuation_date=v_date,
                                           value_per_unit=row.get('value_per_unit', 0)))
            cache_valuation.add(key)
            bump('asset_valuations', True)
    DB.session.flush()

    # ── AssetDisposal (clé heuristique : lot local + date + qté + prix de vente) ─
    # Même convention que AssetPossession : tx_id/source_split_id/dest_split_id ne sont pas
    # ré-établis, la donnée fiscale/patrimoniale (quantité cédée, prix, date, plus-value réalisée)
    # est préservée intégralement. possession_id est résolu via map_possession construit ci-dessus.
    existing_disposals = AssetDisposal.query.filter_by(user_id=user_id).all()
    cache_disposal = {
        (d.possession_id, d.sale_date, d.quantity, d.sale_price) for d in existing_disposals
    }
    for row in payload.get('asset_disposals', []):
        possession_local = map_possession.get(row.get('possession_id'))
        if not possession_local:
            report.setdefault('errors', []).append("Cession d'actif ignorée (lot introuvable)")
            continue
        sale_date = _parse_dt(row.get('sale_date'))
        key = (possession_local, sale_date, row.get('quantity'), _dec(row.get('sale_price')))
        if key in cache_disposal:
            bump('asset_disposals', False)
        else:
            DB.session.add(AssetDisposal(
                user_id=user_id, possession_id=possession_local, quantity=row.get('quantity', 0),
                sale_price=row.get('sale_price'), sale_price_native=row.get('sale_price_native'),
                sale_date=sale_date, dest_account_id=map_account.get(row.get('dest_account_id')),
                realized_gain=row.get('realized_gain'), holding_period_days=row.get('holding_period_days')))
            cache_disposal.add(key)
            bump('asset_disposals', True)
    DB.session.flush()

    # ── Transactions + Splits + TagsOnSplits ─────────────────────────────────
    # Clé de correspondance (comme l'import CSV/QIF, étendue à toute la transaction plutôt qu'un
    # seul split) : même date + même description + même multiset de (compte local, montant) sur
    # l'ensemble des splits. Les comptes/catégories référencés doivent avoir été résolus avant.
    existing_tx = Transactions.query.filter_by(user_id=user_id).all()
    existing_tx_ids = [t.id for t in existing_tx]
    existing_splits = Splits.query.filter(Splits.tx_id.in_(existing_tx_ids)).all() if existing_tx_ids else []
    splits_by_tx = {}
    for s in existing_splits:
        splits_by_tx.setdefault(s.tx_id, []).append(s)

    def tx_signature(post_date, description, split_pairs):
        return (post_date.date() if post_date else None, description or '', tuple(sorted(split_pairs)))

    cache_tx = {}
    for t in existing_tx:
        pairs = [(s.account_id, s.quantity) for s in splits_by_tx.get(t.id, [])]
        cache_tx[tx_signature(t.post_date, t.description, pairs)] = t

    map_split = {}
    for row in payload.get('transactions', []):
        currency_local = map_commodity.get(row.get('currency_id'))
        if not currency_local:
            report.setdefault('errors', []).append(f"Transaction '{row.get('description')}' ignorée (devise introuvable)")
            continue
        tx_splits = [s for s in payload.get('splits', []) if s['tx_id'] == row['id']]
        remapped_pairs = []
        valid = True
        for s in tx_splits:
            acc_local = map_account.get(s.get('account_id'))
            if not acc_local:
                valid = False
                break
            remapped_pairs.append((acc_local, _dec(s.get('quantity'))))
        if not valid:
            report.setdefault('errors', []).append(f"Transaction '{row.get('description')}' ignorée (compte introuvable)")
            continue

        post_date = _parse_dt(row.get('post_date'))
        sig = tx_signature(post_date, row.get('description'), remapped_pairs)
        existing = cache_tx.get(sig)
        if existing:
            map_tx[row['id']] = existing.id
            bump('transactions', False)
            # Résout les splits export -> splits locaux existants pour les tags_on_split, en
            # consommant chaque split local au plus une fois (cas de deux splits identiques
            # dans la même transaction, ex. montant nul en double).
            local_splits = list(splits_by_tx.get(existing.id, []))
            for s in tx_splits:
                acc_local = map_account.get(s.get('account_id'))
                qty = _dec(s.get('quantity'))
                for i, ls in enumerate(local_splits):
                    if ls.account_id == acc_local and _dec(ls.quantity) == qty:
                        map_split[s['id']] = ls.id
                        del local_splits[i]
                        break
                bump('splits', False)
        else:
            tx = Transactions(
                user_id=user_id, currency_id=currency_local, post_date=post_date,
                effective_date=_parse_dt(row.get('effective_date'), post_date),
                description=row.get('description'), category_id=map_category.get(row.get('category_id')),
                is_cleared=row.get('is_cleared', False))
            DB.session.add(tx)
            DB.session.flush()
            cache_tx[sig] = tx
            map_tx[row['id']] = tx.id
            bump('transactions', True)
            for s in tx_splits:
                split = Splits(tx_id=tx.id, account_id=map_account.get(s.get('account_id')),
                              quantity=s.get('quantity', 0), is_reconciled=s.get('is_reconciled', False),
                              description=s.get('description'), fx_rate=s.get('fx_rate', 1))
                DB.session.add(split)
                DB.session.flush()
                map_split[s['id']] = split.id
                bump('splits', True)

    for row in payload.get('tags_on_split', []):
        split_local, tag_local = map_split.get(row['split_id']), map_tag.get(row['tag_id'])
        if not (split_local and tag_local):
            continue
        if not TagsOnSplits.query.filter_by(split_id=split_local, tag_id=tag_local).first():
            DB.session.add(TagsOnSplits(split_id=split_local, tag_id=tag_local))
            bump('tags_on_split', True)
        else:
            bump('tags_on_split', False)

    # ── TransactionDocuments (clé : transaction + empreinte du fichier) ─────
    existing_docs = TransactionDocuments.query.filter_by(user_id=user_id, status='confirmed').all()
    cache_doc = {(d.tx_id, hashlib.sha256(d.file_data).hexdigest()) for d in existing_docs}
    for row in payload.get('transaction_documents', []):
        tx_local = map_tx.get(row.get('tx_id'))
        if not tx_local:
            report.setdefault('errors', []).append(f"Justificatif '{row.get('original_filename')}' ignoré (transaction introuvable)")
            continue
        try:
            file_bytes = base64.b64decode(row['file_data_b64'])
        except Exception:
            report.setdefault('errors', []).append(f"Justificatif '{row.get('original_filename')}' ignoré (fichier illisible)")
            continue
        key = (tx_local, hashlib.sha256(file_bytes).hexdigest())
        if key in cache_doc:
            bump('transaction_documents', False)
        else:
            DB.session.add(TransactionDocuments(
                tx_id=tx_local, user_id=user_id, original_filename=row.get('original_filename', 'document'),
                mime_type=row.get('mime_type', 'application/octet-stream'), file_data=file_bytes,
                status='confirmed'))
            cache_doc.add(key)
            bump('transaction_documents', True)

    # ── UserSettings (jamais écrasé sans confirmation explicite) ─────────────
    if apply_settings and payload.get('user_settings'):
        us = payload['user_settings']
        settings = UserSettings.query.filter_by(user_id=user_id).first()
        if not settings:
            settings = UserSettings(user_id=user_id)
            DB.session.add(settings)
        settings.currency = us.get('currency', settings.currency if settings.currency else 'EUR')
        settings.date_format = us.get('date_format', 'fr-FR')
        settings.market_score_weights = us.get('market_score_weights')
        settings.market_score_thresholds = us.get('market_score_thresholds')
        report['user_settings'] = {'applied': True}
    else:
        report['user_settings'] = {'applied': False}

    return report


class BackupRoutes:
    def __init__(self, app, DB, Users, Commodities, Accounts, Categories, Tags, Budgets, BudgetAccounts,
                 BudgetCategories, BudgetTags, Subscriptions, Assets, AssetPossession, AssetDisposal,
                 AssetValuations, Transactions, Splits, TagsOnSplits, UserSettings, TransactionDocuments):
        ROUTE_PATH = f"{ROOT_PATH}/backup"

        @app.route(f"{ROUTE_PATH}/export", methods=['GET'])
        @jwt_required()
        def export_backup():
            user_id = get_jwt_identity()
            data, doc_files = export_user_data(user_id, DB, Commodities, Accounts, Categories, Tags, Budgets,
                                    BudgetAccounts, BudgetCategories, BudgetTags, Subscriptions, Assets,
                                    AssetPossession, AssetDisposal, AssetValuations, Transactions, Splits,
                                    TagsOnSplits, UserSettings, TransactionDocuments)
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('data.json', json_lib.dumps(data, ensure_ascii=False, indent=2))
                for doc_file in doc_files:
                    zf.writestr(doc_file['path'], doc_file['bytes'])
            buffer.seek(0)
            filename = f"cantisa-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
            return Response(
                buffer.getvalue(),
                mimetype='application/zip',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'})

        @app.route(f"{ROUTE_PATH}/import", methods=['POST'])
        @jwt_required()
        def import_backup():
            file = request.files.get('file')
            if not file:
                return json_response('Aucun fichier fourni', HttpCode.BAD_REQUEST)
            apply_settings = request.form.get('apply_settings', 'false').lower() == 'true'
            raw = file.stream.read()
            try:
                if zipfile.is_zipfile(io.BytesIO(raw)):
                    # Nouveau format (archive .zip) : data.json + fichiers de documents/ à côté,
                    # référencés par 'file_path' — on les recharge en base64 pour retomber sur la
                    # même forme de payload qu'attend import_user_data (inchangé depuis le format
                    # JSON pur, pour ne pas dupliquer la logique de dédoublonnage).
                    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                        payload = json_lib.loads(zf.read('data.json').decode('utf-8-sig'))
                        for doc in payload.get('transaction_documents', []):
                            doc_path = doc.pop('file_path', None)
                            if doc_path:
                                doc['file_data_b64'] = base64.b64encode(zf.read(doc_path)).decode('ascii')
                else:
                    # Ancien format (JSON pur, éventuellement avec 'file_data_b64' déjà embarqué) :
                    # toujours accepté pour ne pas casser la réimportation de sauvegardes antérieures.
                    payload = json_lib.loads(raw.decode('utf-8-sig'))
            except (json_lib.JSONDecodeError, UnicodeDecodeError, KeyError, zipfile.BadZipFile):
                return json_response('Fichier de sauvegarde invalide', HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            try:
                report = import_user_data(user_id, payload, DB, Commodities, Accounts, Categories, Tags,
                                          Budgets, BudgetAccounts, BudgetCategories, BudgetTags, Subscriptions,
                                          Assets, AssetPossession, AssetDisposal, AssetValuations, Transactions,
                                          Splits, TagsOnSplits, UserSettings, TransactionDocuments,
                                          apply_settings=apply_settings)
                DB.session.commit()
                return json_response(report, HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
