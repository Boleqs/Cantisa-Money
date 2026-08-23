from datetime import datetime, timedelta, date

from apscheduler.schedulers.background import BackgroundScheduler


def _price_at(SubscriptionPriceHistory, sub, exec_date):
    """Prix en vigueur à exec_date : dernière entrée d'historique dont effective_date <= exec_date,
    repli sur sub.amount (abonnement pas encore migré / historique introuvable)."""
    if SubscriptionPriceHistory is None:
        return sub.amount
    h = (SubscriptionPriceHistory.query
         .filter(SubscriptionPriceHistory.subscription_id == sub.id,
                 SubscriptionPriceHistory.effective_date <= exec_date)
         .order_by(SubscriptionPriceHistory.effective_date.desc())
         .first())
    return h.amount if h else sub.amount


def _execute_subscription(sub, exec_date, DB, Transactions, Splits, Accounts, SubscriptionPriceHistory=None):
    from_account = Accounts.query.filter_by(id=sub.from_account_id).first()
    if not from_account:
        return
    amount = _price_at(SubscriptionPriceHistory, sub, exec_date)
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
    DB.session.add(Splits(tx_id=tx.id, account_id=sub.from_account_id, quantity=-amount))
    DB.session.add(Splits(tx_id=tx.id, account_id=sub.to_account_id, quantity=amount))
    sub.last_executed_at = exec_dt


def execute_due_subscriptions(app, DB, Subscriptions, Transactions, Splits, Accounts, SubscriptionPriceHistory=None):
    """Crée les transactions pour tous les abonnements échus. Appelé par le scheduler.
    Chaque échéance de rattrapage est facturée au prix qui était réellement en vigueur à sa date
    (via SubscriptionPriceHistory), pas au prix courant de l'abonnement — voir _price_at()."""
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
                _execute_subscription(sub, next_due, DB, Transactions, Splits, Accounts, SubscriptionPriceHistory)
                next_due = next_occurrence(
                    sub.schedule_type, sub.day_of_month, sub.month_of_year, sub.weekdays, next_due)
        DB.session.commit()


def execute_one_subscription(sub, exec_date, DB, Transactions, Splits, Accounts, SubscriptionPriceHistory=None):
    """Exécute un abonnement unique pour une date donnée (appel manuel)."""
    _execute_subscription(sub, exec_date, DB, Transactions, Splits, Accounts, SubscriptionPriceHistory)
    DB.session.commit()


def _execute_loan_installment(installment, loan, DB, Transactions, Splits, Accounts):
    payment_account = Accounts.query.filter_by(id=loan.payment_account_id).first()
    if not payment_account:
        return
    exec_dt = datetime.combine(installment.due_date, datetime.min.time())
    tx = Transactions(
        user_id=loan.user_id,
        currency_id=payment_account.currency_id,
        post_date=exec_dt,
        effective_date=exec_dt,
        description=f"Échéance prêt {loan.name} #{installment.installment_number}",
        category_id=loan.category_id,
        is_cleared=True,
    )
    DB.session.add(tx)
    DB.session.flush()
    DB.session.add(Splits(tx_id=tx.id, account_id=loan.payment_account_id, quantity=-installment.total_amount))
    DB.session.add(Splits(tx_id=tx.id, account_id=loan.liability_account_id, quantity=installment.principal_portion))
    if loan.insurance_expense_account_id and installment.insurance_portion:
        DB.session.add(Splits(
            tx_id=tx.id, account_id=loan.interest_expense_account_id, quantity=installment.interest_portion))
        DB.session.add(Splits(
            tx_id=tx.id, account_id=loan.insurance_expense_account_id, quantity=installment.insurance_portion))
    else:
        # Pas de compte d'assurance dédié -> assurance fondue dans la ligne d'intérêts (choix
        # utilisateur à la création du prêt, voir rt_loans.py).
        DB.session.add(Splits(
            tx_id=tx.id, account_id=loan.interest_expense_account_id,
            quantity=installment.interest_portion + installment.insurance_portion))
    installment.is_paid = True
    installment.paid_at = exec_dt
    installment.transaction_id = tx.id


def execute_due_loan_installments(app, DB, Loans, LoanInstallments, Transactions, Splits, Accounts):
    """Poste les échéances dues pour tous les prêts en auto_debit=True (rattrape les échéances en
    retard, comme execute_due_subscriptions). Les prêts à validation manuelle (auto_debit=False,
    par défaut) ne sont jamais touchés ici — voir POST /loans/execute. Appelé par le scheduler."""
    with app.app_context():
        today = date.today()
        loans = Loans.query.filter(Loans.auto_debit == True, Loans.is_closed == False).all()
        for loan in loans:
            due = LoanInstallments.query.filter(
                LoanInstallments.loan_id == loan.id,
                LoanInstallments.is_paid == False,
                LoanInstallments.due_date <= today,
            ).order_by(LoanInstallments.installment_number).all()
            for inst in due:
                _execute_loan_installment(inst, loan, DB, Transactions, Splits, Accounts)
        DB.session.commit()


def execute_one_loan_installment(installment, loan, DB, Transactions, Splits, Accounts):
    """Exécution manuelle d'une échéance unique (bouton 'Exécuter' / POST /loans/execute)."""
    _execute_loan_installment(installment, loan, DB, Transactions, Splits, Accounts)
    DB.session.commit()


def _execute_dca_contribution(plan, exec_date, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits):
    """Exécute une échéance DCA unique : achète l'actif du plan au prix de marché courant pour le
    montant prévu, crée le lot de portefeuille correspondant. Retourne (success: bool,
    error: str|None). N'avance last_executed_at QUE si un lot a effectivement été créé — une
    échéance en échec (FX/prix indisponible) reste due et sera retentée à la prochaine passe horaire
    (execute_due_dca_contributions) ou au clic manuel (execute_one_dca_contribution)."""
    from backend.utils.portfolio_ops import resolve_dca_unit_price, compute_dca_quantity, resolve_split_amounts, create_possession_lot, format_qty

    asset = Assets.query.filter_by(id=plan.asset_id).first()
    source_account = Accounts.query.filter_by(id=plan.source_account_id).first()
    dest_account = Accounts.query.filter_by(id=plan.dest_account_id).first()
    if not (asset and source_account and dest_account):
        return False, "Actif ou compte introuvable (supprimé depuis la création du plan)"
    commodity = Commodities.query.filter_by(id=asset.commodity_id).first()
    if not commodity:
        return False, "Devise de l'actif introuvable"

    unit_price, unit_price_native, err = resolve_dca_unit_price(asset, commodity, FxRates)
    if err:
        return False, err

    source_commodity = Commodities.query.filter_by(id=source_account.currency_id).first()
    source_code = source_commodity.short_name if source_commodity else commodity.short_name
    quantity, err = compute_dca_quantity(plan.amount, source_code, commodity.short_name, unit_price, FxRates)
    if err:
        return False, err

    total_cost = float(quantity) * unit_price
    dest_amount, source_amount, dest_fx_rate, error_resp = resolve_split_amounts(
        Accounts, Commodities, dest_account, source_account, total_cost, commodity.short_name, exec_date, FxRates)
    if error_resp:
        return False, "Taux de change indisponible pour l'exécution"

    exec_dt = datetime.combine(exec_date, datetime.min.time())
    create_possession_lot(
        DB, Transactions, Splits, AssetPossession, plan.user_id, asset, dest_account, source_account,
        quantity=quantity, purchase_price=unit_price, purchase_price_native=unit_price_native,
        purchase_date=exec_dt, description=f"DCA {plan.name} — {asset.symbol} x{format_qty(quantity)}",
        dest_amount=dest_amount, source_amount=source_amount, dest_fx_rate=dest_fx_rate,
        dca_plan_id=plan.id)
    plan.last_executed_at = exec_dt
    return True, None


def execute_due_dca_contributions(app, DB, DcaPlans, Assets, AssetPossession, Commodities, FxRates, Accounts, Transactions, Splits):
    """Rattrape toutes les échéances DCA dues (comme execute_due_subscriptions). Appelé par le
    scheduler."""
    from backend.utils.recurrence import next_occurrence
    with app.app_context():
        today = date.today()
        plans = DcaPlans.query.filter(DcaPlans.is_forecast_only == False).all()
        for plan in plans:
            ref = plan.last_executed_at.date() if plan.last_executed_at else (plan.start_date - timedelta(days=1))
            next_due = next_occurrence(plan.schedule_type, plan.day_of_month, plan.month_of_year, plan.weekdays, ref)
            while next_due <= today and (plan.end_date is None or next_due <= plan.end_date):
                _execute_dca_contribution(plan, next_due, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits)
                next_due = next_occurrence(plan.schedule_type, plan.day_of_month, plan.month_of_year, plan.weekdays, next_due)
        DB.session.commit()


def execute_one_dca_contribution(plan, exec_date, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits):
    """Exécution manuelle (bouton 'Exécuter' / POST /dca/execute). Retourne (success, error_message)
    pour que la route puisse afficher un message d'erreur réel — contrairement aux abonnements, un
    DCA peut légitimement échouer (FX/prix indisponible)."""
    success, error = _execute_dca_contribution(plan, exec_date, DB, Accounts, Assets, AssetPossession, Commodities, FxRates, Transactions, Splits)
    DB.session.commit()
    return success, error


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


def snapshot_wealth(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, WealthSnapshot, Splits, snapshot_user_id=None):
    """Enregistre un point quotidien (bancaire + portefeuille, converti en EUR) par utilisateur (ou
    un seul si `snapshot_user_id` est fourni — cf. rt_assets.py::_force_wealth_refresh, appelé après
    chaque achat/vente/suppression de position : recalculer tous les utilisateurs à chaque fois
    serait un gaspillage inutile, contributeur direct de la latence perçue sur ces actions). Appelé
    par le scheduler et une fois au démarrage (voir app.py)."""
    from utils.wealth import compute_bank_net_worth, compute_total_liabilities, get_portfolio_container_account_values
    with app.app_context():
        today = date.today()
        user_ids = {snapshot_user_id} if snapshot_user_id is not None else {row[0] for row in DB.session.query(Accounts.user_id).distinct()}
        for user_id in user_ids:
            bank_nw = compute_bank_net_worth(Accounts, Commodities, AssetPossession, FxRates, user_id, 'EUR')
            # Positions + cash libre des comptes-conteneurs (pas juste les positions) — même
            # raisonnement que rt_wealth.py::get_wealth_overview : compute_bank_net_worth exclut ces
            # comptes pour ne pas compter leur coût d'achat figé, donc leur cash libre doit être
            # compté ici, sous peine de disparaître du Patrimoine.
            container_values = get_portfolio_container_account_values(
                Accounts, Assets, AssetPossession, AssetDisposal, Splits, Commodities, FxRates, user_id, 'EUR')
            portfolio_val = round(sum(container_values.values()), 2)
            liabilities = compute_total_liabilities(Accounts, Commodities, FxRates, user_id, 'EUR')
            # bank_nw/portfolio_val restent bruts (soldes bancaires + portefeuille, sans dette) —
            # seul le total (le "Patrimoine") est net des crédits en cours.
            total = round(bank_nw + portfolio_val - liabilities, 2)
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


def renew_due_budgets(app, DB, Budgets, BudgetAccounts, BudgetCategories, BudgetTags, FxRates, Commodities, UserSettings):
    """Reconduit automatiquement les budgets dont la période est terminée et qui ont un
    renew_period défini : crée le budget de la période suivante (mêmes comptes/catégories/tags,
    même montant alloué), en décalant start_date/end_date d'une période calendaire (mois civil,
    pas juste +30 jours, pour ne pas dériver). `renewed` protège contre une double reconduction si
    le job tourne plusieurs fois avant que la nouvelle période ne soit à son tour dépassée. Appelé
    par le scheduler."""
    from dateutil.relativedelta import relativedelta
    from backend.routes.rt_budgets import _recompute_budget_spent

    deltas = {
        'monthly': relativedelta(months=1),
        'quarterly': relativedelta(months=3),
        'yearly': relativedelta(years=1),
    }
    with app.app_context():
        now = datetime.now()
        due = Budgets.query.filter(
            Budgets.renew_period.isnot(None),
            Budgets.renewed == False,
            Budgets.end_date < now,
        ).all()
        for old in due:
            delta = deltas.get(old.renew_period)
            if not delta:
                continue
            new_budget = Budgets(
                user_id=old.user_id,
                name=old.name,
                amount_allocated=old.amount_allocated,
                amount_spent=0,
                renew_period=old.renew_period,
                renewed=False,
                start_date=old.start_date + delta,
                end_date=old.end_date + delta,
            )
            DB.session.add(new_budget)
            DB.session.flush()
            for ba in BudgetAccounts.query.filter_by(budget_id=old.id).all():
                DB.session.add(BudgetAccounts(budget_id=new_budget.id, account_id=ba.account_id))
            for bc in BudgetCategories.query.filter_by(budget_id=old.id).all():
                DB.session.add(BudgetCategories(budget_id=new_budget.id, category_id=bc.category_id))
            for bt in BudgetTags.query.filter_by(budget_id=old.id).all():
                DB.session.add(BudgetTags(budget_id=new_budget.id, tag_id=bt.tag_id))
            DB.session.flush()
            _recompute_budget_spent(DB, new_budget.id, Budgets, FxRates, Commodities, UserSettings)
            old.renewed = True
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


def backfill_wealth_history_job(app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations):
    """Rattrape l'historique pour toute date d'achat pas encore couverte (ex: nouvel actif ajouté
    avec une date d'achat passée pendant que le backend tournait déjà). Appelé par le scheduler."""
    from utils.wealth import backfill_wealth_history
    with app.app_context():
        backfill_wealth_history(DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations)


def start_scheduler(app, DB, Subscriptions, Transactions, Splits, Accounts, Assets, Commodities, FxRates,
                     AssetPossession, AssetDisposal, WealthSnapshot, UserSettings, TransactionDocuments, AssetValuations,
                     Loans, LoanInstallments, Budgets, BudgetAccounts, BudgetCategories, BudgetTags, DcaPlans,
                     SubscriptionPriceHistory=None):
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
        args=[app, DB, Subscriptions, Transactions, Splits, Accounts, SubscriptionPriceHistory],
        trigger='interval',
        hours=1,
        id='subscriptions_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=execute_due_loan_installments,
        args=[app, DB, Loans, LoanInstallments, Transactions, Splits, Accounts],
        trigger='interval',
        hours=1,
        id='loan_installments_job',
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
        args=[app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, Transactions, Splits, WealthSnapshot, AssetValuations],
        trigger='interval',
        hours=24,
        id='wealth_backfill_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=snapshot_wealth,
        args=[app, DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates, WealthSnapshot, Splits],
        trigger='interval',
        hours=24,
        id='wealth_snapshot_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=renew_due_budgets,
        args=[app, DB, Budgets, BudgetAccounts, BudgetCategories, BudgetTags, FxRates, Commodities, UserSettings],
        trigger='interval',
        hours=1,
        id='budget_renewal_job',
        replace_existing=True,
    )
    scheduler.add_job(
        func=execute_due_dca_contributions,
        args=[app, DB, DcaPlans, Assets, AssetPossession, Commodities, FxRates, Accounts, Transactions, Splits],
        trigger='interval',
        hours=1,
        id='dca_contributions_job',
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
