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


def _financial_doc_zip_path(doc_id, original_filename):
    """Équivalent de _doc_zip_path pour le coffre-fort de documents financiers (rt_financial_documents.py)
    — préfixe distinct pour ne pas mélanger les deux familles de documents dans l'archive."""
    safe_name = os.path.basename(original_filename or 'document').strip() or 'document'
    return f"financial_documents/{doc_id}_{safe_name}"


# ── Remapping des références UUID à l'intérieur d'un config JSONB opaque ────
# (CustomReports.config.filters) : le backend ne les interprète pas autrement, mais elles
# pointent vers des comptes/catégories/tags dont l'id local change à chaque import — sans ce
# remapping, un rapport personnalisé restauré filtrerait sur des ids qui n'existent plus.
_CUSTOM_REPORT_ID_FIELDS = {'account_id': 'account', 'category_id': 'category', 'tag_id': 'tag'}


def _remap_custom_report_filters(filters, maps):
    remapped = []
    for f in filters or []:
        field = f.get('field')
        map_key = _CUSTOM_REPORT_ID_FIELDS.get(field)
        if map_key is None:
            remapped.append(f)
            continue
        m = maps[map_key]
        value = f.get('value')
        # str() : les ids locaux résolus via map_account/map_category/map_tag sont des uuid.UUID
        # (colonnes UUID SQLAlchemy), non sérialisables tels quels dans une colonne JSONB.
        if isinstance(value, list):
            new_value = [str(m[v]) for v in value if v in m]
            if not new_value:
                continue
        else:
            if value not in m:
                continue
            new_value = str(m[value])
        remapped.append({**f, 'value': new_value})
    return remapped


def export_user_data(user_id, DB, Commodities, Accounts, Categories, Tags, Budgets, BudgetAccounts,
                      BudgetCategories, BudgetTags, Subscriptions, Assets, AssetPossession, AssetDisposal,
                      AssetValuations, Transactions, Splits, TagsOnSplits, UserSettings,
                      TransactionDocuments, Institutions=None, SubscriptionPriceHistory=None,
                      DcaPlans=None, TaxRegime=None, TaxHouseholdProfile=None, TaxHouseholdIncome=None,
                      FinancialGoals=None, ImportCategoryRules=None, Watchlist=None, CustomReports=None,
                      Loans=None, LoanInstallments=None, LoanRateRevisions=None, FinancialDocuments=None):
    commodities = Commodities.query.filter_by(user_id=user_id).all()
    accounts = Accounts.query.filter_by(user_id=user_id).all()
    institutions = Institutions.query.filter_by(user_id=user_id).all() if Institutions is not None else []
    categories = Categories.query.filter_by(user_id=user_id).all()
    tags = Tags.query.filter_by(user_id=user_id).all()
    budgets = Budgets.query.filter_by(user_id=user_id).all()
    budget_ids = [b.id for b in budgets]
    budget_accounts = BudgetAccounts.query.filter(BudgetAccounts.budget_id.in_(budget_ids)).all() if budget_ids else []
    budget_categories = BudgetCategories.query.filter(BudgetCategories.budget_id.in_(budget_ids)).all() if budget_ids else []
    budget_tags = BudgetTags.query.filter(BudgetTags.budget_id.in_(budget_ids)).all() if budget_ids else []
    subscriptions = Subscriptions.query.filter_by(user_id=user_id).all()
    sub_ids = [s.id for s in subscriptions]
    sub_price_history = (SubscriptionPriceHistory.query.filter(SubscriptionPriceHistory.subscription_id.in_(sub_ids)).all()
                          if SubscriptionPriceHistory is not None and sub_ids else [])
    assets = Assets.query.filter_by(user_id=user_id).all()
    asset_possessions = AssetPossession.query.filter_by(user_id=user_id).all()
    asset_disposals = AssetDisposal.query.filter_by(user_id=user_id).all()
    asset_valuations = AssetValuations.query.filter_by(user_id=user_id).all()
    dca_plans = DcaPlans.query.filter_by(user_id=user_id).all() if DcaPlans is not None else []
    tax_regimes = TaxRegime.query.filter_by(user_id=user_id).all() if TaxRegime is not None else []
    household_profiles = TaxHouseholdProfile.query.filter_by(user_id=user_id).all() if TaxHouseholdProfile is not None else []
    household_ids = [h.id for h in household_profiles]
    household_incomes = (TaxHouseholdIncome.query.filter(TaxHouseholdIncome.household_profile_id.in_(household_ids)).all()
                          if TaxHouseholdIncome is not None and household_ids else [])
    financial_goals = FinancialGoals.query.filter_by(user_id=user_id).all() if FinancialGoals is not None else []
    import_category_rules = ImportCategoryRules.query.filter_by(user_id=user_id).all() if ImportCategoryRules is not None else []
    watchlist = Watchlist.query.filter_by(user_id=user_id).all() if Watchlist is not None else []
    custom_reports = CustomReports.query.filter_by(user_id=user_id).all() if CustomReports is not None else []
    loans = Loans.query.filter_by(user_id=user_id).all() if Loans is not None else []
    loan_ids = [l.id for l in loans]
    loan_rate_revisions = (LoanRateRevisions.query.filter(LoanRateRevisions.loan_id.in_(loan_ids)).all()
                            if LoanRateRevisions is not None and loan_ids else [])
    loan_installments = (LoanInstallments.query.filter(LoanInstallments.loan_id.in_(loan_ids)).all()
                          if LoanInstallments is not None and loan_ids else [])
    transactions = Transactions.query.filter_by(user_id=user_id).all()
    tx_ids = [t.id for t in transactions]
    splits = Splits.query.filter(Splits.tx_id.in_(tx_ids)).all() if tx_ids else []
    split_ids = [s.id for s in splits]
    tags_on_split = TagsOnSplits.query.filter(TagsOnSplits.split_id.in_(split_ids)).all() if split_ids else []
    settings = UserSettings.query.filter_by(user_id=user_id).first()
    # Seuls les justificatifs confirmés (rattachés à une transaction) sont de vraies données
    # utilisateur — 'pending' est un état transitoire de relecture OCR en cours, jamais persistant.
    documents = TransactionDocuments.query.filter_by(user_id=user_id, status='confirmed').all()
    financial_documents = FinancialDocuments.query.filter_by(user_id=user_id).all() if FinancialDocuments is not None else []

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
            'institution_id': _u(a.institution_id),
        } for a in accounts],
        'institutions': [{
            'id': _u(i.id), 'name': i.name, 'bic': i.bic, 'website': i.website, 'notes': i.notes,
            'color': i.color,
        } for i in institutions],
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
        'subscription_price_history': [{
            'id': _u(h.id), 'subscription_id': _u(h.subscription_id), 'effective_date': _dt(h.effective_date),
            'amount': _n(h.amount),
        } for h in sub_price_history],
        'assets': [{
            'id': _u(a.id), 'symbol': a.symbol, 'name': a.name, 'asset_type': a.asset_type, 'sector': a.sector,
            'commodity_id': _u(a.commodity_id), 'value_per_unit': _n(a.value_per_unit),
            'track_live_price': a.track_live_price,
        } for a in assets],
        'asset_possessions': [{
            'id': _u(p.id), 'asset_id': _u(p.asset_id), 'account_id': _u(p.account_id),
            'source_account_id': _u(p.source_account_id), 'quantity': _n(p.quantity),
            'purchase_price': _n(p.purchase_price), 'purchase_price_native': _n(p.purchase_price_native),
            'fees': _n(p.fees), 'fx_rate': _n(p.fx_rate), 'purchase_date': _dt(p.purchase_date),
        } for p in asset_possessions],
        # tx_id/source_split_id/dest_split_id volontairement absents, même raison que pour
        # asset_possessions (voir commentaire dans import_user_data) — la donnée fiscale/patrimoniale
        # (quantité, prix, date, plus-value) est préservée intégralement sans reconstituer les splits.
        'asset_disposals': [{
            'id': _u(d.id), 'possession_id': _u(d.possession_id), 'quantity': _n(d.quantity),
            'sale_price': _n(d.sale_price), 'sale_price_native': _n(d.sale_price_native), 'fees': _n(d.fees),
            'fx_rate': _n(d.fx_rate),
            'sale_date': _dt(d.sale_date), 'dest_account_id': _u(d.dest_account_id),
            'realized_gain': _n(d.realized_gain), 'holding_period_days': d.holding_period_days,
        } for d in asset_disposals],
        'asset_valuations': [{
            'id': _u(v.id), 'asset_id': _u(v.asset_id), 'valuation_date': _dt(v.valuation_date),
            'value_per_unit': _n(v.value_per_unit),
        } for v in asset_valuations],
        'dca_plans': [{
            'id': _u(p.id), 'name': p.name, 'asset_id': _u(p.asset_id),
            'source_account_id': _u(p.source_account_id), 'dest_account_id': _u(p.dest_account_id),
            'amount': _n(p.amount), 'schedule_type': p.schedule_type, 'day_of_month': p.day_of_month,
            'month_of_year': p.month_of_year, 'weekdays': p.weekdays, 'start_date': _dt(p.start_date),
            'end_date': _dt(p.end_date), 'is_forecast_only': p.is_forecast_only,
            'last_executed_at': _dt(p.last_executed_at),
        } for p in dca_plans],
        'tax_regime': [{
            'id': _u(r.id), 'name': r.name, 'country_code': r.country_code, 'tax_year': r.tax_year,
            'config': r.config, 'is_active': r.is_active, 'is_verified': r.is_verified,
        } for r in tax_regimes],
        'tax_household_profile': [{
            'id': _u(h.id), 'tax_year': h.tax_year, 'adults': h.adults, 'dependents': h.dependents,
            'dependents_disabled': h.dependents_disabled, 'parent_isole': h.parent_isole, 'notes': h.notes,
        } for h in household_profiles],
        'tax_household_income': [{
            'id': _u(i.id), 'household_profile_id': _u(i.household_profile_id), 'label': i.label,
            'amount': _n(i.amount), 'income_type': i.income_type,
        } for i in household_incomes],
        'financial_goals': [{
            'id': _u(g.id), 'name': g.name, 'goal_type': g.goal_type, 'target_amount': _n(g.target_amount),
            'target_date': _dt(g.target_date), 'end_date': _dt(g.end_date),
        } for g in financial_goals],
        'import_category_rules': [{
            'id': _u(r.id), 'keyword': r.keyword, 'category_id': _u(r.category_id),
            'opposing_account_id': _u(r.opposing_account_id),
        } for r in import_category_rules],
        'watchlist': [{'id': _u(w.id), 'ticker': w.ticker} for w in watchlist],
        'custom_reports': [{
            'id': _u(r.id), 'name': r.name, 'config': r.config,
        } for r in custom_reports],
        'loans': [{
            'id': _u(l.id), 'name': l.name, 'principal': _n(l.principal), 'annual_rate': _n(l.annual_rate),
            'term_months': l.term_months, 'start_date': _dt(l.start_date), 'payment_day': l.payment_day,
            'payment_account_id': _u(l.payment_account_id),
            'interest_expense_account_id': _u(l.interest_expense_account_id),
            'insurance_expense_account_id': _u(l.insurance_expense_account_id),
            'insurance_monthly_amount': _n(l.insurance_monthly_amount),
            'liability_account_id': _u(l.liability_account_id),
            'equity_opening_account_id': _u(l.equity_opening_account_id),
            'opening_transaction_id': _u(l.opening_transaction_id), 'category_id': _u(l.category_id),
            'auto_debit': l.auto_debit, 'is_existing_loan': l.is_existing_loan, 'is_closed': l.is_closed,
            'closed_at': _dt(l.closed_at),
        } for l in loans],
        'loan_rate_revisions': [{
            'id': _u(r.id), 'loan_id': _u(r.loan_id), 'effective_date': _dt(r.effective_date),
            'new_annual_rate': _n(r.new_annual_rate), 'recalc_mode': r.recalc_mode,
        } for r in loan_rate_revisions],
        'loan_installments': [{
            'id': _u(i.id), 'loan_id': _u(i.loan_id), 'installment_number': i.installment_number,
            'due_date': _dt(i.due_date), 'principal_portion': _n(i.principal_portion),
            'interest_portion': _n(i.interest_portion), 'insurance_portion': _n(i.insurance_portion),
            'total_amount': _n(i.total_amount), 'remaining_principal_after': _n(i.remaining_principal_after),
            'is_paid': i.is_paid, 'paid_at': _dt(i.paid_at), 'transaction_id': _u(i.transaction_id),
            'rate_revision_id': _u(i.rate_revision_id),
        } for i in loan_installments],
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
        # Même principe que transaction_documents ci-dessus : bytes réels à part dans l'archive
        # (voir financial_doc_files plus bas), seul le chemin est référencé ici.
        'financial_documents': [{
            'id': _u(d.id), 'original_filename': d.original_filename, 'mime_type': d.mime_type,
            'category': d.category, 'description': d.description, 'extracted_text': d.extracted_text,
            'linked_account_id': _u(d.linked_account_id), 'linked_asset_id': _u(d.linked_asset_id),
            'linked_loan_id': _u(d.linked_loan_id), 'uploaded_at': _dt(d.uploaded_at),
            'file_path': _financial_doc_zip_path(d.id, d.original_filename),
        } for d in financial_documents],
        'user_settings': ({
            'currency': settings.currency, 'date_format': settings.date_format,
            'market_score_weights': settings.market_score_weights,
            'market_score_thresholds': settings.market_score_thresholds,
        } if settings else None),
    }
    doc_files = [{'path': _doc_zip_path(d.id, d.original_filename), 'bytes': d.file_data} for d in documents]
    doc_files += [{'path': _financial_doc_zip_path(d.id, d.original_filename), 'bytes': d.file_data}
                  for d in financial_documents]

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
                      TransactionDocuments, apply_settings=False, Institutions=None,
                      SubscriptionPriceHistory=None, DcaPlans=None, TaxRegime=None, TaxHouseholdProfile=None,
                      TaxHouseholdIncome=None, FinancialGoals=None, ImportCategoryRules=None, Watchlist=None,
                      CustomReports=None, Loans=None, LoanInstallments=None, LoanRateRevisions=None,
                      FinancialDocuments=None):
    report = {}

    def bump(entity, created):
        r = report.setdefault(entity, {'created': 0, 'matched': 0})
        r['created' if created else 'matched'] += 1

    # id export -> id local, un dict par type d'entité (les UUID d'export ne sont pas globalement
    # uniques entre types, ex. rien ne garantit qu'un id de compte ne collisionne pas avec un id de
    # catégorie dans deux exports différents concaténés à la main).
    map_commodity, map_account, map_category, map_tag = {}, {}, {}, {}
    map_budget, map_subscription, map_asset, map_tx = {}, {}, {}, {}
    map_possession, map_institution = {}, {}
    map_household_profile, map_loan, map_loan_rate_revision = {}, {}, {}

    # ── Institutions (clé : nom) ─────────────────────────────────────────────
    if Institutions is not None:
        cache_institution = {i.name: i for i in Institutions.query.filter_by(user_id=user_id).all()}
        for row in payload.get('institutions', []):
            existing = cache_institution.get(row['name'])
            if existing:
                map_institution[row['id']] = existing.id
                bump('institutions', False)
            else:
                obj = Institutions(user_id=user_id, name=row['name'], bic=row.get('bic'),
                                   website=row.get('website'), notes=row.get('notes'),
                                   color=row.get('color', 'blue'))
                DB.session.add(obj)
                DB.session.flush()
                cache_institution[row['name']] = obj
                map_institution[row['id']] = obj.id
                bump('institutions', True)

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
                    institution_id=map_institution.get(row.get('institution_id')),
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

    # ── SubscriptionPriceHistory (clé : abonnement + date d'effet) ──────────
    if SubscriptionPriceHistory is not None:
        existing_sph = SubscriptionPriceHistory.query.filter_by(user_id=user_id).all()
        cache_sph = {(h.subscription_id, h.effective_date) for h in existing_sph}
        for row in payload.get('subscription_price_history', []):
            sub_local = map_subscription.get(row.get('subscription_id'))
            if not sub_local:
                continue
            eff_date = _parse_date(row.get('effective_date'))
            key = (sub_local, eff_date)
            if key in cache_sph:
                bump('subscription_price_history', False)
            else:
                DB.session.add(SubscriptionPriceHistory(
                    user_id=user_id, subscription_id=sub_local, effective_date=eff_date,
                    amount=row.get('amount', 0)))
                cache_sph.add(key)
                bump('subscription_price_history', True)

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
        key = (asset_local, account_local, purchase_date, _dec(row.get('quantity')), _dec(row.get('purchase_price')))
        existing_id = cache_possession.get(key)
        if existing_id:
            map_possession[row['id']] = existing_id
            bump('asset_possessions', False)
        else:
            obj = AssetPossession(
                user_id=user_id, asset_id=asset_local, account_id=account_local,
                source_account_id=map_account.get(row.get('source_account_id')),
                quantity=row.get('quantity', 0), purchase_price=row.get('purchase_price'),
                purchase_price_native=row.get('purchase_price_native'), fees=row.get('fees', 0),
                fx_rate=row.get('fx_rate'), purchase_date=purchase_date)
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
        key = (possession_local, sale_date, _dec(row.get('quantity')), _dec(row.get('sale_price')))
        if key in cache_disposal:
            bump('asset_disposals', False)
        else:
            DB.session.add(AssetDisposal(
                user_id=user_id, possession_id=possession_local, quantity=row.get('quantity', 0),
                sale_price=row.get('sale_price'), sale_price_native=row.get('sale_price_native'),
                fees=row.get('fees', 0), fx_rate=row.get('fx_rate'),
                sale_date=sale_date, dest_account_id=map_account.get(row.get('dest_account_id')),
                realized_gain=row.get('realized_gain'), holding_period_days=row.get('holding_period_days')))
            cache_disposal.add(key)
            bump('asset_disposals', True)
    DB.session.flush()

    # ── DcaPlans (clé : nom) ──────────────────────────────────────────────────
    if DcaPlans is not None:
        cache_dca = {p.name: p for p in DcaPlans.query.filter_by(user_id=user_id).all()}
        for row in payload.get('dca_plans', []):
            existing = cache_dca.get(row['name'])
            if existing:
                bump('dca_plans', False)
            else:
                asset_local = map_asset.get(row.get('asset_id'))
                source_local = map_account.get(row.get('source_account_id'))
                dest_local = map_account.get(row.get('dest_account_id'))
                if not (asset_local and source_local and dest_local):
                    report.setdefault('errors', []).append(f"Plan DCA '{row.get('name')}' ignoré (référence introuvable)")
                    continue
                obj = DcaPlans(
                    user_id=user_id, name=row['name'], asset_id=asset_local, source_account_id=source_local,
                    dest_account_id=dest_local, amount=row.get('amount', 0),
                    schedule_type=row.get('schedule_type', 'monthly'), day_of_month=row.get('day_of_month'),
                    month_of_year=row.get('month_of_year'), weekdays=row.get('weekdays'),
                    start_date=_parse_date(row.get('start_date')), end_date=_parse_date(row.get('end_date')),
                    is_forecast_only=row.get('is_forecast_only', False),
                    last_executed_at=_parse_dt(row.get('last_executed_at')))
                DB.session.add(obj)
                cache_dca[row['name']] = obj
                bump('dca_plans', True)
        DB.session.flush()

    # ── TaxRegime (clé : nom) ─────────────────────────────────────────────────
    if TaxRegime is not None:
        cache_tax_regime = {r.name: r for r in TaxRegime.query.filter_by(user_id=user_id).all()}
        for row in payload.get('tax_regime', []):
            existing = cache_tax_regime.get(row['name'])
            if existing:
                bump('tax_regime', False)
            else:
                obj = TaxRegime(
                    user_id=user_id, name=row['name'], country_code=row.get('country_code', 'FR'),
                    tax_year=row['tax_year'], config=row.get('config', {}),
                    is_active=row.get('is_active', False), is_verified=row.get('is_verified', False))
                DB.session.add(obj)
                cache_tax_regime[row['name']] = obj
                bump('tax_regime', True)
        DB.session.flush()

    # ── TaxHouseholdProfile (clé : année fiscale) + TaxHouseholdIncome ───────
    if TaxHouseholdProfile is not None:
        cache_household = {h.tax_year: h for h in TaxHouseholdProfile.query.filter_by(user_id=user_id).all()}
        for row in payload.get('tax_household_profile', []):
            existing = cache_household.get(row['tax_year'])
            if existing:
                map_household_profile[row['id']] = existing.id
                bump('tax_household_profile', False)
            else:
                obj = TaxHouseholdProfile(
                    user_id=user_id, tax_year=row['tax_year'], adults=row.get('adults', 1),
                    dependents=row.get('dependents', 0), dependents_disabled=row.get('dependents_disabled', 0),
                    parent_isole=row.get('parent_isole', False), notes=row.get('notes'))
                DB.session.add(obj)
                DB.session.flush()
                cache_household[row['tax_year']] = obj
                map_household_profile[row['id']] = obj.id
                bump('tax_household_profile', True)
        DB.session.flush()

        if TaxHouseholdIncome is not None:
            existing_incomes = TaxHouseholdIncome.query.filter(
                TaxHouseholdIncome.household_profile_id.in_(list(map_household_profile.values()))
            ).all() if map_household_profile else []
            cache_income = {(i.household_profile_id, i.label, _dec(i.amount), i.income_type) for i in existing_incomes}
            for row in payload.get('tax_household_income', []):
                profile_local = map_household_profile.get(row.get('household_profile_id'))
                if not profile_local:
                    continue
                key = (profile_local, row['label'], _dec(row.get('amount')), row.get('income_type', 'other'))
                if key in cache_income:
                    bump('tax_household_income', False)
                else:
                    DB.session.add(TaxHouseholdIncome(
                        household_profile_id=profile_local, label=row['label'], amount=row.get('amount', 0),
                        income_type=row.get('income_type', 'other')))
                    cache_income.add(key)
                    bump('tax_household_income', True)
            DB.session.flush()

    # ── FinancialGoals (clé heuristique : nom + échéance + montant) ─────────
    if FinancialGoals is not None:
        existing_goals = FinancialGoals.query.filter_by(user_id=user_id).all()
        target_dt_by_row = {}
        cache_goal = set()
        for g in existing_goals:
            cache_goal.add((g.name, g.target_date, _dec(g.target_amount)))
        for row in payload.get('financial_goals', []):
            target_date = _parse_dt(row.get('target_date'))
            key = (row['name'], target_date, _dec(row.get('target_amount')))
            if key in cache_goal:
                bump('financial_goals', False)
            else:
                DB.session.add(FinancialGoals(
                    user_id=user_id, name=row['name'], goal_type=row.get('goal_type', 'one_time'),
                    target_amount=row.get('target_amount', 0), target_date=target_date,
                    end_date=_parse_dt(row.get('end_date'))))
                cache_goal.add(key)
                bump('financial_goals', True)
        DB.session.flush()

    # ── ImportCategoryRules (clé : mot-clé) ──────────────────────────────────
    if ImportCategoryRules is not None:
        cache_rule = {r.keyword: r for r in ImportCategoryRules.query.filter_by(user_id=user_id).all()}
        for row in payload.get('import_category_rules', []):
            existing = cache_rule.get(row['keyword'])
            if existing:
                bump('import_category_rules', False)
            else:
                DB.session.add(ImportCategoryRules(
                    user_id=user_id, keyword=row['keyword'],
                    category_id=map_category.get(row.get('category_id')),
                    opposing_account_id=map_account.get(row.get('opposing_account_id'))))
                cache_rule[row['keyword']] = row
                bump('import_category_rules', True)
        DB.session.flush()

    # ── Watchlist (clé : ticker) ──────────────────────────────────────────────
    if Watchlist is not None:
        cache_watchlist = {w.ticker for w in Watchlist.query.filter_by(user_id=user_id).all()}
        for row in payload.get('watchlist', []):
            if row['ticker'] in cache_watchlist:
                bump('watchlist', False)
            else:
                DB.session.add(Watchlist(user_id=user_id, ticker=row['ticker']))
                cache_watchlist.add(row['ticker'])
                bump('watchlist', True)
        DB.session.flush()

    # ── CustomReports (clé heuristique : nom) ────────────────────────────────
    # config.filters peut référencer des account_id/category_id/tag_id de l'export — remappés vers
    # les ids locaux (map_account/map_category/map_tag déjà résolus ci-dessus), sinon un rapport
    # restauré filtrerait sur des ids qui n'existent plus dans cette instance.
    if CustomReports is not None:
        cache_custom_report = {r.name: r for r in CustomReports.query.filter_by(user_id=user_id).all()}
        maps = {'account': map_account, 'category': map_category, 'tag': map_tag}
        for row in payload.get('custom_reports', []):
            existing = cache_custom_report.get(row['name'])
            if existing:
                bump('custom_reports', False)
            else:
                config = dict(row.get('config') or {})
                config['filters'] = _remap_custom_report_filters(config.get('filters'), maps)
                DB.session.add(CustomReports(user_id=user_id, name=row['name'], config=config))
                cache_custom_report[row['name']] = row
                bump('custom_reports', True)
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

    # ── Loans + LoanRateRevisions + LoanInstallments ─────────────────────────
    # Importés après les transactions : Loans.opening_transaction_id référence l'écriture
    # d'ouverture du crédit, qui doit déjà exister localement (map_tx) pour être remappée.
    if Loans is not None:
        cache_loan = {l.name: l for l in Loans.query.filter_by(user_id=user_id).all()}
        for row in payload.get('loans', []):
            existing = cache_loan.get(row['name'])
            if existing:
                map_loan[row['id']] = existing.id
                bump('loans', False)
            else:
                payment_acc = map_account.get(row.get('payment_account_id'))
                interest_acc = map_account.get(row.get('interest_expense_account_id'))
                liability_acc = map_account.get(row.get('liability_account_id'))
                if not (payment_acc and interest_acc and liability_acc):
                    report.setdefault('errors', []).append(f"Prêt '{row.get('name')}' ignoré (compte introuvable)")
                    continue
                obj = Loans(
                    user_id=user_id, name=row['name'], principal=row.get('principal', 0),
                    annual_rate=row.get('annual_rate', 0), term_months=row.get('term_months', 1),
                    start_date=_parse_date(row.get('start_date')), payment_day=row.get('payment_day', 1),
                    payment_account_id=payment_acc, interest_expense_account_id=interest_acc,
                    insurance_expense_account_id=map_account.get(row.get('insurance_expense_account_id')),
                    insurance_monthly_amount=row.get('insurance_monthly_amount'),
                    liability_account_id=liability_acc,
                    equity_opening_account_id=map_account.get(row.get('equity_opening_account_id')),
                    opening_transaction_id=map_tx.get(row.get('opening_transaction_id')),
                    category_id=map_category.get(row.get('category_id')),
                    auto_debit=row.get('auto_debit', False), is_existing_loan=row.get('is_existing_loan', False),
                    is_closed=row.get('is_closed', False), closed_at=_parse_dt(row.get('closed_at')))
                DB.session.add(obj)
                DB.session.flush()
                cache_loan[row['name']] = obj
                map_loan[row['id']] = obj.id
                bump('loans', True)
        DB.session.flush()

        if LoanRateRevisions is not None:
            existing_revisions = LoanRateRevisions.query.filter(
                LoanRateRevisions.loan_id.in_(list(map_loan.values()))
            ).all() if map_loan else []
            cache_revision = {}
            for r in existing_revisions:
                cache_revision.setdefault((r.loan_id, r.effective_date, _dec(r.new_annual_rate)), r)
            for row in payload.get('loan_rate_revisions', []):
                loan_local = map_loan.get(row.get('loan_id'))
                if not loan_local:
                    continue
                eff_date = _parse_date(row.get('effective_date'))
                key = (loan_local, eff_date, _dec(row.get('new_annual_rate')))
                existing = cache_revision.get(key)
                if existing:
                    map_loan_rate_revision[row['id']] = existing.id
                    bump('loan_rate_revisions', False)
                else:
                    obj = LoanRateRevisions(
                        loan_id=loan_local, effective_date=eff_date,
                        new_annual_rate=row.get('new_annual_rate', 0),
                        recalc_mode=row.get('recalc_mode', 'keep_term'))
                    DB.session.add(obj)
                    DB.session.flush()
                    cache_revision[key] = obj
                    map_loan_rate_revision[row['id']] = obj.id
                    bump('loan_rate_revisions', True)
            DB.session.flush()

        if LoanInstallments is not None:
            existing_installments = LoanInstallments.query.filter(
                LoanInstallments.loan_id.in_(list(map_loan.values()))
            ).all() if map_loan else []
            cache_installment = {(i.loan_id, i.installment_number) for i in existing_installments}
            for row in payload.get('loan_installments', []):
                loan_local = map_loan.get(row.get('loan_id'))
                if not loan_local:
                    continue
                key = (loan_local, row['installment_number'])
                if key in cache_installment:
                    bump('loan_installments', False)
                else:
                    DB.session.add(LoanInstallments(
                        loan_id=loan_local, installment_number=row['installment_number'],
                        due_date=_parse_date(row.get('due_date')),
                        principal_portion=row.get('principal_portion', 0),
                        interest_portion=row.get('interest_portion', 0),
                        insurance_portion=row.get('insurance_portion', 0),
                        total_amount=row.get('total_amount', 0),
                        remaining_principal_after=row.get('remaining_principal_after', 0),
                        is_paid=row.get('is_paid', False), paid_at=_parse_dt(row.get('paid_at')),
                        transaction_id=map_tx.get(row.get('transaction_id')),
                        rate_revision_id=map_loan_rate_revision.get(row.get('rate_revision_id'))))
                    cache_installment.add(key)
                    bump('loan_installments', True)
            DB.session.flush()

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

    # ── FinancialDocuments (clé : empreinte du fichier — pas de transaction à laquelle
    # rattacher la clé, contrairement à TransactionDocuments) ───────────────
    if FinancialDocuments is not None:
        existing_fin_docs = FinancialDocuments.query.filter_by(user_id=user_id).all()
        cache_fin_doc = {hashlib.sha256(d.file_data).hexdigest() for d in existing_fin_docs}
        for row in payload.get('financial_documents', []):
            category = row.get('category')
            if not category:
                report.setdefault('errors', []).append(
                    f"Document financier '{row.get('original_filename')}' ignoré (catégorie manquante)")
                continue
            try:
                file_bytes = base64.b64decode(row['file_data_b64'])
            except Exception:
                report.setdefault('errors', []).append(
                    f"Document financier '{row.get('original_filename')}' ignoré (fichier illisible)")
                continue
            key = hashlib.sha256(file_bytes).hexdigest()
            if key in cache_fin_doc:
                bump('financial_documents', False)
            else:
                DB.session.add(FinancialDocuments(
                    user_id=user_id, original_filename=row.get('original_filename', 'document'),
                    mime_type=row.get('mime_type', 'application/octet-stream'), file_data=file_bytes,
                    file_size=len(file_bytes),
                    category=category, description=row.get('description'),
                    extracted_text=row.get('extracted_text'),
                    linked_account_id=map_account.get(row.get('linked_account_id')),
                    linked_asset_id=map_asset.get(row.get('linked_asset_id')),
                    linked_loan_id=map_loan.get(row.get('linked_loan_id')),
                    uploaded_at=_parse_dt(row.get('uploaded_at')) or datetime.now()))
                cache_fin_doc.add(key)
                bump('financial_documents', True)

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
                 AssetValuations, Transactions, Splits, TagsOnSplits, UserSettings, TransactionDocuments,
                 Institutions=None, SubscriptionPriceHistory=None, DcaPlans=None, TaxRegime=None,
                 TaxHouseholdProfile=None, TaxHouseholdIncome=None, FinancialGoals=None,
                 ImportCategoryRules=None, Watchlist=None, CustomReports=None, Loans=None,
                 LoanInstallments=None, LoanRateRevisions=None, FinancialDocuments=None):
        ROUTE_PATH = f"{ROOT_PATH}/backup"

        @app.route(f"{ROUTE_PATH}/export", methods=['GET'])
        @jwt_required()
        def export_backup():
            user_id = get_jwt_identity()
            data, doc_files = export_user_data(user_id, DB, Commodities, Accounts, Categories, Tags, Budgets,
                                    BudgetAccounts, BudgetCategories, BudgetTags, Subscriptions, Assets,
                                    AssetPossession, AssetDisposal, AssetValuations, Transactions, Splits,
                                    TagsOnSplits, UserSettings, TransactionDocuments, Institutions,
                                    SubscriptionPriceHistory, DcaPlans, TaxRegime, TaxHouseholdProfile,
                                    TaxHouseholdIncome, FinancialGoals, ImportCategoryRules, Watchlist,
                                    CustomReports, Loans, LoanInstallments, LoanRateRevisions,
                                    FinancialDocuments=FinancialDocuments)
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
                        for doc in payload.get('financial_documents', []):
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
                                          apply_settings=apply_settings, Institutions=Institutions,
                                          SubscriptionPriceHistory=SubscriptionPriceHistory, DcaPlans=DcaPlans,
                                          TaxRegime=TaxRegime, TaxHouseholdProfile=TaxHouseholdProfile,
                                          TaxHouseholdIncome=TaxHouseholdIncome, FinancialGoals=FinancialGoals,
                                          ImportCategoryRules=ImportCategoryRules, Watchlist=Watchlist,
                                          CustomReports=CustomReports, Loans=Loans,
                                          LoanInstallments=LoanInstallments, LoanRateRevisions=LoanRateRevisions,
                                          FinancialDocuments=FinancialDocuments)
                DB.session.commit()
                return json_response(report, HttpCode.OK)
            except Exception as e:
                DB.session.rollback()
                return json_response(str(e), HttpCode.SERVER_ERROR)
