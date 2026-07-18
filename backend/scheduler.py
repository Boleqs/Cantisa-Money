from datetime import datetime, timedelta, date

from apscheduler.schedulers.background import BackgroundScheduler


def _execute_subscription(sub, exec_date, DB, Transactions, Splits, Accounts):
    from_account = Accounts.query.filter_by(id=sub.from_account_id).first()
    if not from_account:
        return
    exec_dt = datetime.combine(exec_date, datetime.min.time())
    tx = Transactions(
        user_id=sub.user_id,
        currency_id=from_account.currency_id,
        post_date=exec_dt,
        effective_date=exec_dt,
        description=sub.name,
        category_id=sub.category_id,
        is_cleared=True,
    )
    DB.session.add(tx)
    DB.session.flush()
    DB.session.add(Splits(tx_id=tx.id, account_id=sub.from_account_id, quantity=-sub.amount))
    DB.session.add(Splits(tx_id=tx.id, account_id=sub.to_account_id, quantity=sub.amount))
    sub.last_executed_at = exec_dt


def execute_due_subscriptions(app, DB, Subscriptions, Transactions, Splits, Accounts):
    """Crée les transactions pour tous les abonnements échus. Appelé par le scheduler."""
    from utils.recurrence import next_occurrence
    with app.app_context():
        today = date.today()
        # Prévisionnel uniquement : jamais exécuté automatiquement (pas de transaction créée),
        # sert juste d'échéance affichée — voir _next_due() dans rt_subscriptions.py.
        subs = Subscriptions.query.filter(Subscriptions.is_forecast_only == False).all()
        for sub in subs:
            ref = sub.last_executed_at.date() if sub.last_executed_at else sub.created_at.date()
            next_due = next_occurrence(sub.schedule_type, sub.day_of_month, sub.month_of_year, sub.weekdays, ref)
            while next_due <= today:
                _execute_subscription(sub, next_due, DB, Transactions, Splits, Accounts)
                next_due = next_occurrence(
                    sub.schedule_type, sub.day_of_month, sub.month_of_year, sub.weekdays, next_due)
        DB.session.commit()


def execute_one_subscription(sub, exec_date, DB, Transactions, Splits, Accounts):
    """Exécute un abonnement unique pour une date donnée (appel manuel)."""
    _execute_subscription(sub, exec_date, DB, Transactions, Splits, Accounts)
    DB.session.commit()


def refresh_tracked_asset_prices(app, DB, Assets, Commodities, FxRates):
    """Rafraîchit value_per_unit (converti dans la devise de l'actif) pour tous les actifs
    suivis en temps réel. Appelé par le scheduler."""
    from utils.market_price import fetch_live_prices_bulk, convert_amount
    with app.app_context():
        tracked = Assets.query.filter(Assets.track_live_price == True).all()
        if not tracked:
            return
        results = fetch_live_prices_bulk([a.symbol for a in tracked])
        commodities_by_id = {c.id: c for c in Commodities.query.all()}
        for a in tracked:
            r = results.get(a.symbol)
            commodity = commodities_by_id.get(a.commodity_id)
            if not (r and r['valid'] and r['price'] is not None and commodity):
                continue
            converted = convert_amount(r['price'], r['currency'], commodity.short_name, FxRates)
            if converted is None:
                continue
            a.value_per_unit = converted
            a.last_price_updated_at = datetime.now()
        DB.session.commit()


def refresh_tracked_commodity_rates(app, DB, Commodities, FxRates, UserSettings):
    """Rafraîchit et met en cache le taux de change de chaque commodity suivie automatiquement,
    contre la devise par défaut actuelle de son propriétaire (UserSettings.currency). Appelé par
    le scheduler."""
    from utils.market_price import get_fx_rate
    with app.app_context():
        tracked = Commodities.query.filter(Commodities.track_live_rate == True).all()
        if not tracked:
            return
        settings_by_user = {s.user_id: s for s in UserSettings.query.all()}
        for c in tracked:
            settings = settings_by_user.get(c.user_id)
            target_currency = settings.currency if settings else 'EUR'
            if c.short_name == target_currency:
                continue
            rate = get_fx_rate(c.short_name, target_currency, FxRates)
            if rate is None:
                continue
            c.last_rate_updated_at = datetime.now()
        DB.session.commit()


def snapshot_wealth(app, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, WealthSnapshot):
    """Enregistre un point quotidien (bancaire + portefeuille, converti en EUR) par utilisateur.
    Appelé par le scheduler et une fois au démarrage (voir app.py)."""
    from utils.wealth import compute_bank_net_worth, compute_portfolio_value
    with app.app_context():
        today = date.today()
        user_ids = {row[0] for row in DB.session.query(Accounts.user_id).distinct()}
        for user_id in user_ids:
            bank_nw = compute_bank_net_worth(Accounts, Commodities, AssetPossession, FxRates, user_id, 'EUR')
            portfolio_val = compute_portfolio_value(Assets, AssetPossession, Commodities, FxRates, user_id, 'EUR')
            total = round(bank_nw + portfolio_val, 2)
            existing = WealthSnapshot.query.filter_by(user_id=user_id, snapshot_date=today).first()
            if existing:
                existing.bank_net_worth = bank_nw
                existing.portfolio_value = portfolio_val
                existing.total = total
            else:
                DB.session.add(WealthSnapshot(
                    user_id=user_id, snapshot_date=today,
                    bank_net_worth=bank_nw, portfolio_value=portfolio_val, total=total,
                ))
        DB.session.commit()


def cleanup_pending_documents(app, DB, TransactionDocuments):
    """Supprime les tickets/factures uploadés jamais confirmés après 24h (flux OCR abandonné en
    cours de route). Appelé par le scheduler."""
    with app.app_context():
        cutoff = datetime.now() - timedelta(hours=24)
        TransactionDocuments.query.filter(
            TransactionDocuments.status == 'pending',
            TransactionDocuments.uploaded_at < cutoff,
        ).delete()
        DB.session.commit()


def backfill_wealth_history_job(app, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations):
    """Rattrape l'historique pour toute date d'achat pas encore couverte (ex: nouvel actif ajouté
    avec une date d'achat passée pendant que le backend tournait déjà). Appelé par le scheduler."""
    from utils.wealth import backfill_wealth_history
    with app.app_context():
        backfill_wealth_history(DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations)


def start_scheduler(app, DB, Subscriptions, Transactions, Splits, Accounts, Assets, Commodities, FxRates,
                     AssetPossession, WealthSnapshot, UserSettings, TransactionDocuments, AssetValuations):
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=cleanup_pending_documents,
        args=[app, DB, TransactionDocuments],
        trigger='interval',
        hours=24,
        id='pending_documents_cleanup_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=execute_due_subscriptions,
        args=[app, DB, Subscriptions, Transactions, Splits, Accounts],
        trigger='interval',
        hours=1,
        id='subscriptions_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=refresh_tracked_asset_prices,
        args=[app, DB, Assets, Commodities, FxRates],
        trigger='interval',
        minutes=15,
        id='asset_price_refresh_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=refresh_tracked_commodity_rates,
        args=[app, DB, Commodities, FxRates, UserSettings],
        trigger='interval',
        minutes=15,
        id='commodity_rate_refresh_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=backfill_wealth_history_job,
        args=[app, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations],
        trigger='interval',
        hours=24,
        id='wealth_backfill_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=snapshot_wealth,
        args=[app, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, WealthSnapshot],
        trigger='interval',
        hours=24,
        id='wealth_snapshot_job',
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
