from datetime import date, timedelta

from backend.utils.market_price import convert_amount, get_price_series, get_fx_rate_series, fetch_live_price


def compute_bank_net_worth(Accounts, Commodities, user_id, target_currency='EUR'):
    """Somme des comptes Current/Assets/Equity (comme WEALTH_TYPES dans rt_dashboard.py), convertie."""
    accounts = Accounts.query.filter(
        Accounts.user_id == user_id,
        Accounts.account_type.in_(('Current', 'Assets', 'Equity'))
    ).all()
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}

    total = 0.0
    for a in accounts:
        balance = float(a.total_earned or 0) - float(a.total_spent or 0)
        commodity = commodities_by_id.get(a.currency_id)
        code = commodity.short_name if commodity else target_currency
        total += convert_amount(balance, code, target_currency) or 0
    return round(total, 2)


def get_portfolio_breakdown(Assets, AssetPossession, Commodities, user_id, target_currency='EUR'):
    """Retourne la liste enrichie des actifs (valeur + plus-value converties dans target_currency).
    La plus-value est agrégée sur les lots (AssetPossession) qui ont un prix d'achat renseigné —
    les lots sans prix d'achat comptent dans la valeur actuelle mais pas dans la plus-value."""
    assets = Assets.query.filter_by(user_id=user_id).all()
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}

    result = []
    for a in assets:
        possessions = AssetPossession.query.filter_by(asset_id=a.id).all()
        qty = sum(p.quantity for p in possessions)
        commodity = commodities_by_id.get(a.commodity_id)
        code = commodity.short_name if commodity else target_currency

        value = convert_amount(qty * float(a.value_per_unit or 0), code, target_currency) or 0

        priced_qty = sum(p.quantity for p in possessions if p.purchase_price is not None)
        purchase_value = None
        if priced_qty:
            raw_purchase_total = sum(p.quantity * float(p.purchase_price) for p in possessions if p.purchase_price is not None)
            purchase_value = convert_amount(raw_purchase_total, code, target_currency)

        priced_value = convert_amount(priced_qty * float(a.value_per_unit or 0), code, target_currency) if priced_qty else None

        gain_abs = round(priced_value - purchase_value, 2) if purchase_value is not None else None
        gain_pct = round((priced_value - purchase_value) / purchase_value * 100, 2) if purchase_value else None

        result.append({
            'symbol': a.symbol,
            'name': a.name,
            'asset_type': a.asset_type,
            'sector': a.sector,
            'currency': code,
            'quantity': qty,
            'value': round(value, 2),
            'purchase_value': round(purchase_value, 2) if purchase_value is not None else None,
            'gain_abs': gain_abs,
            'gain_pct': gain_pct,
        })
    return result


def compute_portfolio_value(Assets, AssetPossession, Commodities, user_id, target_currency='EUR'):
    breakdown = get_portfolio_breakdown(Assets, AssetPossession, Commodities, user_id, target_currency)
    return round(sum(a['value'] for a in breakdown), 2)


def _day_range(start_date, end_date):
    return [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]


def daily_bank_net_worth_series(Accounts, Commodities, Transactions, Splits, DB, user_id, start_date, end_date, target_currency='EUR'):
    """Reconstruit le solde bancaire net (Current/Assets/Equity, converti) jour par jour sur la période.
    Une seule requête réseau par devise distincte (pas par jour) pour la conversion historique."""
    from sqlalchemy import func

    accounts = Accounts.query.filter(
        Accounts.user_id == user_id,
        Accounts.account_type.in_(('Current', 'Assets', 'Equity'))
    ).all()
    if not accounts:
        return {}
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}
    account_currency = {}
    for a in accounts:
        commodity = commodities_by_id.get(a.currency_id)
        account_currency[a.id] = commodity.short_name if commodity else target_currency
    account_ids = list(account_currency.keys())

    opening_rows = DB.session.query(
        Splits.account_id, func.coalesce(func.sum(Splits.quantity), 0)
    ).join(Transactions, Splits.tx_id == Transactions.id).filter(
        Transactions.user_id == user_id,
        Splits.account_id.in_(account_ids),
        Transactions.post_date < start_date,
    ).group_by(Splits.account_id).all()
    running = {aid: 0.0 for aid in account_ids}
    for aid, total in opening_rows:
        running[aid] = float(total)

    daily_rows = DB.session.query(
        Splits.account_id,
        func.date(Transactions.post_date).label('day'),
        func.sum(Splits.quantity).label('flow')
    ).join(Transactions, Splits.tx_id == Transactions.id).filter(
        Transactions.user_id == user_id,
        Splits.account_id.in_(account_ids),
        Transactions.post_date >= start_date,
    ).group_by(Splits.account_id, func.date(Transactions.post_date)).all()
    flow_map = {}
    for aid, day, flow in daily_rows:
        day = day if isinstance(day, date) else date.fromisoformat(str(day))
        flow_map[(aid, day)] = float(flow)

    fx_series_cache = {code: get_fx_rate_series(code, target_currency, start_date, end_date)
                        for code in set(account_currency.values()) if code != target_currency}
    last_fx = {code: None for code in fx_series_cache}

    result = {}
    for d in _day_range(start_date, end_date):
        day_total = 0.0
        for aid in account_ids:
            running[aid] += flow_map.get((aid, d), 0.0)
            code = account_currency[aid]
            if code == target_currency:
                day_total += running[aid]
                continue
            rate = fx_series_cache[code].get(d)
            if rate is not None:
                last_fx[code] = rate
            if last_fx[code] is not None:
                day_total += running[aid] * last_fx[code]
        result[d] = round(day_total, 2)
    return result


def portfolio_value_series(Assets, AssetPossession, Commodities, user_id, start_date, end_date, target_currency='EUR'):
    """Reconstruit la valeur du portefeuille jour par jour. Actifs suivis en temps réel : cours
    historique réel (yfinance, une requête par actif — partagée par tous ses lots). Actifs manuels :
    valeur actuelle considérée constante. Chaque lot (AssetPossession) démarre sa contribution à sa
    propre date d'achat (ou sa date de création si non renseignée), pas à celle de l'actif."""
    assets = Assets.query.filter_by(user_id=user_id).all()
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}
    all_days = _day_range(start_date, end_date)
    result = {d: 0.0 for d in all_days}
    fx_series_cache = {}

    for a in assets:
        possessions = AssetPossession.query.filter_by(asset_id=a.id).all()
        possessions = [p for p in possessions if p.quantity]
        if not possessions:
            continue

        price_series = {}
        flat_price = None
        if a.track_live_price:
            # Le cours historique yfinance est dans la devise NATIVE du ticker (ex: USD pour MSFT),
            # pas dans commodity_id choisi par l'utilisateur pour l'actif — il ne faut pas les confondre.
            live = fetch_live_price(a.symbol)
            native_currency = live.get('currency') or target_currency
            earliest = min(p.purchase_date.date() if p.purchase_date else p.created_at.date() for p in possessions)
            fetch_from = max(earliest, start_date)
            price_series = get_price_series(a.symbol, fetch_from, end_date)
        else:
            # Actif manuel : value_per_unit est déjà stocké tel quel dans commodity_id (pas de conversion).
            commodity = commodities_by_id.get(a.commodity_id)
            native_currency = commodity.short_name if commodity else target_currency
            flat_price = float(a.value_per_unit or 0)

        if native_currency != target_currency and native_currency not in fx_series_cache:
            fx_series_cache[native_currency] = get_fx_rate_series(native_currency, target_currency, start_date, end_date)

        # Prix unitaire converti, précalculé une fois par jour pour cet actif (partagé par tous ses lots).
        price_by_day = {}
        last_price = flat_price
        last_fx = None
        for d in all_days:
            if a.track_live_price:
                p = price_series.get(d)
                if p is not None:
                    last_price = p
            if native_currency == target_currency:
                rate = 1.0
            else:
                r = fx_series_cache[native_currency].get(d)
                if r is not None:
                    last_fx = r
                rate = last_fx
            if last_price is not None and rate is not None:
                price_by_day[d] = last_price * rate

        for p in possessions:
            inception = p.purchase_date.date() if p.purchase_date else p.created_at.date()
            for d in all_days:
                if d < inception:
                    continue
                unit_value = price_by_day.get(d)
                if unit_value is None:
                    continue
                result[d] += p.quantity * unit_value

    return {d: round(v, 2) for d, v in result.items()}


def backfill_wealth_history(DB, Accounts, Assets, AssetPossession, Commodities, Transactions, Splits, WealthSnapshot):
    """Reconstruit l'historique quotidien du patrimoine (bancaire + portefeuille, en EUR) depuis la
    date d'achat la plus ancienne renseignée jusqu'à aujourd'hui, pour chaque utilisateur. Idempotent :
    ne recalcule jamais un jour déjà présent en base."""
    today = date.today()
    user_ids = {row[0] for row in DB.session.query(Accounts.user_id).distinct()}

    for user_id in user_ids:
        purchase_dates = [p.purchase_date.date() for p in AssetPossession.query.filter_by(user_id=user_id).all() if p.purchase_date]
        if not purchase_dates:
            continue
        start_date = min(purchase_dates)
        if start_date >= today:
            continue

        existing_dates = {s.snapshot_date for s in WealthSnapshot.query.filter(
            WealthSnapshot.user_id == user_id,
            WealthSnapshot.snapshot_date >= start_date,
        ).all()}
        missing_days = [d for d in _day_range(start_date, today) if d not in existing_dates]
        if not missing_days:
            continue

        bank_series = daily_bank_net_worth_series(Accounts, Commodities, Transactions, Splits, DB, user_id, start_date, today, 'EUR')
        portfolio_series = portfolio_value_series(Assets, AssetPossession, Commodities, user_id, start_date, today, 'EUR')

        for d in missing_days:
            bank_val = bank_series.get(d, 0.0)
            portfolio_val = portfolio_series.get(d, 0.0)
            DB.session.add(WealthSnapshot(
                user_id=user_id, snapshot_date=d,
                bank_net_worth=round(bank_val, 2),
                portfolio_value=round(portfolio_val, 2),
                total=round(bank_val + portfolio_val, 2),
            ))
    DB.session.commit()
