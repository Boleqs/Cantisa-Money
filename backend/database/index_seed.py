"""
Composition des indices boursiers, récupérée via la librairie pytickersymbols
plutôt qu'une liste de tickers figée en dur. Les données du package sont
reconstruites automatiquement chaque semaine par son mainteneur ; une mise à
jour se fait donc simplement en bumpant la version de la dépendance.
"""

from pytickersymbols import PyTickerSymbols

# Nom affiché -> clé d'indice pytickersymbols
_INDEX_SOURCES = {
    'S&P 500':       'S&P 500',
    'Nasdaq 100':    'NASDAQ 100',
    'CAC 40':        'CAC_40',
    'DAX 40':        'DAX',
    'FTSE 100':      'FTSE 100',
    'Euro Stoxx 50': 'EURO STOXX 50',
    'AEX':           'AEX',
    'SMI':           'Switzerland 20',
    'IBEX 35':       'IBEX 35',
}


def build_index_data():
    """Retourne {nom_affiché: [tickers Yahoo Finance]} pour chaque indice suivi."""
    stock_data = PyTickerSymbols()
    return {
        display_name: [s['symbol'] for s in stock_data.get_stocks_by_index(source_key) if s.get('symbol')]
        for display_name, source_key in _INDEX_SOURCES.items()
    }
