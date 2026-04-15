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
    with app.app_context():
        today = date.today()
        subs = Subscriptions.query.all()
        for sub in subs:
            ref = sub.last_executed_at.date() if sub.last_executed_at else sub.created_at.date()
            next_due = ref + timedelta(days=sub.recurrence)
            while next_due <= today:
                _execute_subscription(sub, next_due, DB, Transactions, Splits, Accounts)
                next_due += timedelta(days=sub.recurrence)
        DB.session.commit()


def execute_one_subscription(sub, exec_date, DB, Transactions, Splits, Accounts):
    """Exécute un abonnement unique pour une date donnée (appel manuel)."""
    _execute_subscription(sub, exec_date, DB, Transactions, Splits, Accounts)
    DB.session.commit()


def start_scheduler(app, DB, Subscriptions, Transactions, Splits, Accounts):
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=execute_due_subscriptions,
        args=[app, DB, Subscriptions, Transactions, Splits, Accounts],
        trigger='interval',
        hours=1,
        id='subscriptions_job',
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
