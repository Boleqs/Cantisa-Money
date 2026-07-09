from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

import yfinance as yf


def _safe(value, decimals=2):
    try:
        if value is None:
            return None
        return round(float(value), decimals)
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


def get_fx_rate(from_currency: str, to_currency: str, on_date=None) -> float:
    """Taux de conversion from_currency -> to_currency. Si on_date est fourni, utilise
    le cours de clôture historique le plus proche (>=) de cette date, sinon le cours actuel.
    Retourne None si le taux est introuvable."""
    if not from_currency or not to_currency or from_currency == to_currency:
        return 1.0
    pair = f"{from_currency}{to_currency}=X"
    try:
        ticker = yf.Ticker(pair)
        if on_date is None:
            info = ticker.info
            rate = info.get('regularMarketPrice') or info.get('currentPrice')
        else:
            hist = ticker.history(start=on_date, end=on_date + timedelta(days=5))
            if hist.empty:
                return None
            rate = float(hist['Close'].iloc[0])
        return _safe(rate, 6)
    except Exception:
        return None


def convert_amount(amount, from_currency: str, to_currency: str, on_date=None):
    """Convertit amount de from_currency vers to_currency. Retourne None si le taux est introuvable."""
    if amount is None:
        return None
    rate = get_fx_rate(from_currency, to_currency, on_date)
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


def get_fx_rate_series(from_currency: str, to_currency: str, start_date, end_date=None) -> dict:
    """Retourne {date: taux from_currency->to_currency} pour toute la période, en une seule requête."""
    if not from_currency or not to_currency or from_currency == to_currency:
        return {}
    pair = f"{from_currency}{to_currency}=X"
    end_date = end_date or (start_date + timedelta(days=1))
    try:
        hist = yf.Ticker(pair).history(start=start_date, end=end_date + timedelta(days=1))
        if hist.empty:
            return {}
        return {idx.date(): _safe(row['Close'], 6) for idx, row in hist.iterrows()}
    except Exception:
        return {}


def fetch_live_prices_bulk(symbols: list, max_workers: int = 10) -> dict:
    """Retourne {symbol: fetch_live_price(symbol)} pour tous les symbols, en parallèle."""
    unique = list(set(symbols))
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch_live_price, s): s for s in unique}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results
