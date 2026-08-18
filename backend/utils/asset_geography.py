from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf


def _resolve_country(symbol: str):
    try:
        info = yf.Ticker(symbol.strip().upper()).info
    except Exception:
        return None
    if not info or info.get('quoteType') is None:
        return None
    return info.get('country')


def get_countries_bulk(symbols: list, max_workers: int = 10) -> dict:
    """{symbol: country|None} pour une liste de symbols, en parallèle, dédoublonné — même pattern
    que fetch_live_prices_bulk (market_price.py), les mêmes gros holdings revenant dans plusieurs
    ETF (AAPL, MSFT, NVDA...)."""
    unique = list({s.strip().upper() for s in symbols if s})
    if not unique:
        return {}
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_resolve_country, s): s for s in unique}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results


def get_etf_top_holdings(symbol: str) -> list:
    """Retourne [{'symbol','name','weight'(0..1)}] pour le top 10 holdings de l'ETF — Yahoo Finance
    ne fournit jamais la composition complète d'un fonds, seulement ce top 10 (cf. topHoldings de
    l'API quoteSummary). Liste vide si indisponible (ex: ETF obligataire, ticker sans fund data)."""
    try:
        df = yf.Ticker(symbol.strip().upper()).funds_data.top_holdings
    except Exception:
        return []
    if df is None or df.empty:
        return []
    holdings = []
    for idx, row in df.iterrows():
        weight = row.get('Holding Percent')
        try:
            weight = float(weight)
        except (TypeError, ValueError):
            weight = 0.0
        holdings.append({'symbol': str(idx), 'name': row.get('Name'), 'weight': weight})
    return holdings


def compute_country_breakdown(positions: list) -> dict:
    """positions: [{'symbol','asset_type' ('Stock'|'ETF'),'value'}] (value déjà dans la devise
    d'affichage). Répartit chaque position sur le(s) pays de ses titres :
    - Stock : 100% de la valeur -> pays de l'action.
    - ETF : top 10 holdings, poids renormalisés parmi les seules lignes dont le pays est résolu,
      appliqués à la valeur totale de la position (extrapolation assumée du top 10 au fonds entier).
    Les positions sans aucun pays résolu partent dans 'unmapped_value' plutôt que d'être ignorées
    silencieusement. Retourne {'by_country': {country: value}, 'unmapped_value': float}."""
    stocks = [p for p in positions if p['asset_type'] == 'Stock']
    etfs = [p for p in positions if p['asset_type'] == 'ETF']

    stock_countries = get_countries_bulk([p['symbol'] for p in stocks])

    etf_holdings = {p['symbol']: get_etf_top_holdings(p['symbol']) for p in etfs}
    all_holding_symbols = [h['symbol'] for holdings in etf_holdings.values() for h in holdings]
    holding_countries = get_countries_bulk(all_holding_symbols)

    by_country = {}
    unmapped_value = 0.0

    for p in stocks:
        country = stock_countries.get(p['symbol'].strip().upper())
        if country:
            by_country[country] = by_country.get(country, 0.0) + p['value']
        else:
            unmapped_value += p['value']

    for p in etfs:
        holdings = etf_holdings.get(p['symbol'], [])
        known = [(h, holding_countries.get(h['symbol'])) for h in holdings]
        known = [(h, c) for h, c in known if c]
        total_known_weight = sum(h['weight'] for h, _ in known)
        if total_known_weight <= 0:
            unmapped_value += p['value']
            continue
        for h, country in known:
            share = h['weight'] / total_known_weight
            by_country[country] = by_country.get(country, 0.0) + p['value'] * share

    return {'by_country': by_country, 'unmapped_value': unmapped_value}
