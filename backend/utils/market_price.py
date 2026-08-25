import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta, date as date_cls

import yfinance as yf


def _safe(value, decimals=2):
    """yfinance renvoie parfois inf/-inf/nan (ex: ratios calculés sur un résultat ~nul) — non
    finite, donc non sérialisable en JSON strict, d'où le filtrage explicite (voir rt_markets.py)."""
    try:
        if value is None:
            return None
        v = float(value)
        return round(v, decimals) if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def fetch_live_price(symbol: str) -> dict:
    """Retourne {'valid': bool, 'price': float|None, 'currency': str|None, 'error': str|None}."""
    try:
        info = yf.Ticker(symbol.strip().upper()).info
    except Exception as e:
        return {'valid': False, 'price': None, 'currency': None, 'error': str(e)}

    if not info or info.get('quoteType') is None:
        return {'valid': False, 'price': None, 'currency': None, 'error': f"Ticker '{symbol}' introuvable"}

    price = _safe(info.get('currentPrice') or info.get('regularMarketPrice'))
    if price is None:
        return {'valid': True, 'price': None, 'currency': info.get('currency'), 'error': 'Prix indisponible'}

    return {'valid': True, 'price': price, 'currency': info.get('currency'), 'error': None}


def _to_date(on_date):
    if on_date is None:
        return date_cls.today()
    return on_date.date() if hasattr(on_date, 'date') else on_date


def _cache_lookup(FxRates, from_code, to_code, rate_date):
    return FxRates.query.filter_by(from_code=from_code, to_code=to_code, rate_date=rate_date).first()


def _cache_store(FxRates, from_code, to_code, rate_date, rate):
    session = FxRates.query.session
    existing = _cache_lookup(FxRates, from_code, to_code, rate_date)
    if existing:
        existing.rate = rate
    else:
        session.add(FxRates(from_code=from_code, to_code=to_code, rate_date=rate_date, rate=rate))
    session.commit()


def _cache_latest(FxRates, from_code, to_code):
    """Taux le plus récent en cache pour cette paire, quelle que soit la date — repli de dernier
    recours si yfinance est indisponible et qu'aucun taux exact n'est en cache."""
    row = (FxRates.query.filter_by(from_code=from_code, to_code=to_code)
           .order_by(FxRates.rate_date.desc()).first())
    return _safe(row.rate, 6) if row else None


def get_fx_rate(from_currency: str, to_currency: str, FxRates, on_date=None) -> float:
    """Taux de conversion from_currency -> to_currency, mis en cache en base (table fx_rates).
    Ordre de résolution : cache exact pour la date demandée -> yfinance (live ou historique)
    -> dernier taux connu en cache pour la paire (repli, potentiellement obsolète) -> None."""
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1.0

    rate_date = _to_date(on_date)
    cached = _cache_lookup(FxRates, from_currency, to_currency, rate_date)
    if cached:
        return _safe(cached.rate, 6)

    pair = f"{from_currency}{to_currency}=X"
    rate = None
    try:
        ticker = yf.Ticker(pair)
        if on_date is None:
            info = ticker.info
            rate = info.get('regularMarketPrice') or info.get('currentPrice')
        else:
            hist = ticker.history(start=rate_date, end=rate_date + timedelta(days=5))
            if not hist.empty:
                rate = float(hist['Close'].iloc[0])
    except Exception:
        rate = None

    rate = _safe(rate, 6)
    if rate is not None:
        _cache_store(FxRates, from_currency, to_currency, rate_date, rate)
        return rate

    return _cache_latest(FxRates, from_currency, to_currency)


def convert_amount(amount, from_currency: str, to_currency: str, FxRates, on_date=None):
    """Convertit amount de from_currency vers to_currency. Retourne None si le taux est introuvable
    (ni cache exact, ni yfinance, ni repli en cache)."""
    if amount is None:
        return None
    rate = get_fx_rate(from_currency, to_currency, FxRates, on_date)
    if rate is None:
        return None
    return _safe(float(amount) * rate)


def get_price_series(symbol: str, start_date, end_date=None) -> dict:
    """Retourne {date: cours de clôture} pour toute la période, en une seule requête réseau.
    Dict vide si le ticker ou les données sont indisponibles."""
    end_date = end_date or (start_date + timedelta(days=1))
    try:
        hist = yf.Ticker(symbol.strip().upper()).history(start=start_date, end=end_date + timedelta(days=1))
        if hist.empty:
            return {}
        return {idx.date(): _safe(row['Close']) for idx, row in hist.iterrows()}
    except Exception:
        return {}


def get_fx_rate_series(from_currency: str, to_currency: str, FxRates, start_date, end_date=None) -> dict:
    """Retourne {date: taux from_currency->to_currency} pour toute la période. Cache-first par jour,
    complète les jours manquants avec un seul appel yfinance puis les met en cache. Si l'appel réseau
    échoue entièrement et qu'aucun jour n'est en cache, retombe sur le dernier taux connu (série plate)."""
    if not from_currency or not to_currency or from_currency == to_currency:
        return {}
    end_date = end_date or (start_date + timedelta(days=1))

    cached_rows = FxRates.query.filter(
        FxRates.from_code == from_currency, FxRates.to_code == to_currency,
        FxRates.rate_date >= start_date, FxRates.rate_date <= end_date,
    ).all()
    result = {r.rate_date: _safe(r.rate, 6) for r in cached_rows}

    all_days = [start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)]
    missing = [d for d in all_days if d not in result]

    if missing:
        pair = f"{from_currency}{to_currency}=X"
        try:
            hist = yf.Ticker(pair).history(start=start_date, end=end_date + timedelta(days=1))
            if not hist.empty:
                session = FxRates.query.session
                for idx, row in hist.iterrows():
                    d = idx.date()
                    rate = _safe(row['Close'], 6)
                    if rate is None:
                        continue
                    result[d] = rate
                    existing = _cache_lookup(FxRates, from_currency, to_currency, d)
                    if existing:
                        existing.rate = rate
                    else:
                        session.add(FxRates(from_code=from_currency, to_code=to_currency, rate_date=d, rate=rate))
                session.commit()
        except Exception:
            pass

    if not result:
        fallback = _cache_latest(FxRates, from_currency, to_currency)
        if fallback is not None:
            result = {d: fallback for d in all_days}

    return result


def fetch_live_prices_bulk(symbols: list, max_workers: int = 10) -> dict:
    """Retourne {symbol: fetch_live_price(symbol)} pour tous les symbols, en parallèle."""
    unique = list(set(symbols))
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_live_price, s): s for s in unique}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results
