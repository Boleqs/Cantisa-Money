import io
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import yfinance as yf
from flask import request, Response
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission

MARKETS_PERM = VAR_PERMISSIONS_LIST['Patrimoine']['id']


# ── Métriques par défaut (mirror de DEFAULT_METRICS dans marketScore.js) ────
_DEFAULT_METRICS = [
    {'key': 'pe_trailing',      'direction': 'lower',  'great': 10, 'bad': 35},
    {'key': 'pe_forward',       'direction': 'lower',  'great': 10, 'bad': 35},
    {'key': 'pb_ratio',         'direction': 'lower',  'great': 1,  'bad': 5 },
    {'key': 'dividend_yield',   'direction': 'higher', 'great': 5,  'bad': 0 },
    {'key': 'roe',              'direction': 'higher', 'great': 20, 'bad': 0 },
    {'key': 'roa',              'direction': 'higher', 'great': 15, 'bad': 0 },
    {'key': 'net_margin',       'direction': 'higher', 'great': 25, 'bad': 0 },
    {'key': 'gross_margin',     'direction': 'higher', 'great': 60, 'bad': 10},
    {'key': 'operating_margin', 'direction': 'higher', 'great': 25, 'bad': 0 },
]


def _compute_score(stock, weights, thresholds):
    """Réplication Python de computeScore() dans marketScore.js."""
    total_weight  = 0
    weighted_sum  = 0

    for m in _DEFAULT_METRICS:
        key = m['key']
        cfg = weights.get(key, {})
        if not cfg.get('enabled') or not cfg.get('weight'):
            continue
        raw = stock.get(key)
        if raw is None:
            continue
        t     = thresholds.get(key) or {'great': m['great'], 'bad': m['bad']}
        great = float(t['great'])
        bad   = float(t['bad'])
        if m['direction'] == 'lower':
            note = 10 if raw <= great else (0 if raw >= bad else 10 * (bad - raw) / (bad - great))
        else:
            note = 10 if raw >= great else (0 if raw <= bad  else 10 * (raw - bad) / (great - bad))
        w = cfg['weight']
        weighted_sum += note * w
        total_weight += w

    if total_weight == 0:
        return None
    return round((weighted_sum / total_weight) * 10) / 10


def _safe(value, decimals=2):
    """Retourne la valeur arrondie ou None si indisponible. yfinance renvoie parfois inf/-inf/nan
    (ex: trailingPE quand le résultat net est ~nul) — non finite, donc non sérialisable en JSON
    strict (Python écrirait le token invalide `Infinity`/`NaN`), d'où le filtrage explicite."""
    try:
        if value is None:
            return None
        v = float(value)
        return round(v, decimals) if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _raw(value):
    """Retourne la valeur brute (float) sans arrondi, ou None si indisponible/non finie (voir _safe).
    À utiliser pour les décimaux qui seront ensuite multipliés par 100."""
    try:
        if value is None:
            return None
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _fmt_market_cap(value):
    if value is None:
        return None
    try:
        v = float(value)
        if v >= 1e12:
            return f"{v / 1e12:.2f}T"
        if v >= 1e9:
            return f"{v / 1e9:.2f}B"
        if v >= 1e6:
            return f"{v / 1e6:.2f}M"
        return str(int(v))
    except (TypeError, ValueError):
        return None


class MarketsRoutes:
    def __init__(self, app, Users, DB=None, Watchlist=None, MarketIndex=None):
        ROUTE_PATH = f"{ROOT_PATH}/markets"

        @app.route(f"{ROUTE_PATH}/analyse", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def get_market_analyse():
            ticker_symbol = request.args.get('ticker', '').strip().upper()
            if not ticker_symbol:
                return json_response("Paramètre 'ticker' manquant", HttpCode.BAD_REQUEST)

            try:
                ticker = yf.Ticker(ticker_symbol)
                info = ticker.info
            except Exception as e:
                return json_response(f"Erreur lors de la récupération des données : {str(e)}", HttpCode.INTERNAL_SERVER_ERROR)

            # Vérification que le ticker existe
            if not info or info.get('quoteType') is None:
                return json_response(f"Ticker '{ticker_symbol}' introuvable", HttpCode.NOT_FOUND)

            # --- Métriques de valorisation ---
            pe_trailing   = _safe(info.get('trailingPE'))
            pe_forward    = _safe(info.get('forwardPE'))
            pb_ratio      = _safe(info.get('priceToBook'))

            # --- Rentabilité (décimaux bruts, multipliés par 100 à la sortie) ---
            roe              = _raw(info.get('returnOnEquity'))
            roa              = _raw(info.get('returnOnAssets'))
            net_margin       = _raw(info.get('profitMargins'))
            gross_margin     = _raw(info.get('grossMargins'))
            operating_margin = _raw(info.get('operatingMargins'))

            # --- Prix & marché ---
            current_price     = _safe(info.get('currentPrice') or info.get('regularMarketPrice'))
            previous_close    = _safe(info.get('previousClose'))
            week_52_high      = _safe(info.get('fiftyTwoWeekHigh'))
            week_52_low       = _safe(info.get('fiftyTwoWeekLow'))
            market_cap_raw    = info.get('marketCap')
            market_cap        = _fmt_market_cap(market_cap_raw)
            # dividendYield de yfinance est inconsistant (décimal ou % selon le ticker).
            # On recalcule manuellement depuis dividendRate (montant annuel en devise) / prix.
            dividend_rate = _raw(info.get('dividendRate') or info.get('trailingAnnualDividendRate'))
            current_price_raw = _raw(info.get('currentPrice') or info.get('regularMarketPrice'))
            dividend_yield = (
                round(dividend_rate / current_price_raw * 100, 2)
                if dividend_rate and current_price_raw and current_price_raw != 0
                else None
            )

            # Variation jour en %
            day_change_pct = None
            if current_price and previous_close and previous_close != 0:
                day_change_pct = round((current_price - previous_close) / previous_close * 100, 2)

            # --- Identité ---
            result = {
                # Identité
                'ticker':       ticker_symbol,
                'name':         info.get('longName') or info.get('shortName'),
                'sector':       info.get('sector'),
                'industry':     info.get('industry'),
                'country':      info.get('country'),
                'currency':     info.get('currency'),
                'exchange':     info.get('exchange'),

                # Prix
                'current_price':    current_price,
                'previous_close':   previous_close,
                'day_change_pct':   day_change_pct,
                'week_52_high':     week_52_high,
                'week_52_low':      week_52_low,
                'market_cap':       market_cap,

                # Valorisation
                'pe_trailing':  pe_trailing,
                'pe_forward':   pe_forward,
                'pb_ratio':     pb_ratio,

                # Rentabilité (valeurs en %, stockées en décimal dans yfinance)
                'roe':              round(roe * 100, 2) if roe is not None else None,
                'roa':              round(roa * 100, 2) if roa is not None else None,
                'net_margin':       round(net_margin * 100, 2) if net_margin is not None else None,
                'gross_margin':     round(gross_margin * 100, 2) if gross_margin is not None else None,
                'operating_margin': round(operating_margin * 100, 2) if operating_margin is not None else None,
                'dividend_yield':   dividend_yield,
            }

            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/export-pdf", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def export_market_pdf():
            import traceback
            from fpdf import FPDF

            stocks = request.get_json()
            if not stocks or not isinstance(stocks, list):
                return json_response("Corps JSON invalide : liste d'actions attendue", HttpCode.BAD_REQUEST)

            def v(val, unit=''):
                return f"{val}{unit}" if val is not None else '-'

            def rating(label, val, thresholds):
                """Retourne (R, G, B) selon seuils (type, val) -> couleur."""
                if val is None:
                    return (150, 150, 150)
                lo, hi = thresholds
                if lo == 'min':   # plus bas = mieux (P/E, P/B)
                    if val < hi[0]: return (74, 222, 128)
                    if val < hi[1]: return (250, 204, 21)
                    return (248, 113, 113)
                else:             # plus haut = mieux (ROE, marges)
                    if val >= hi[0]: return (74, 222, 128)
                    if val >= hi[1]: return (250, 204, 21)
                    return (248, 113, 113)

            try:
                pdf = FPDF(orientation='P', unit='mm', format='A4')
                pdf.set_margins(14, 14, 14)
                pdf.set_auto_page_break(auto=True, margin=14)

                for stock in stocks:
                    pdf.add_page()

                    # ── En-tête ──────────────────────────────────────────────
                    pdf.set_fill_color(30, 41, 59)
                    pdf.rect(0, 0, 210, 28, 'F')
                    pdf.set_y(8)
                    pdf.set_font('Helvetica', 'B', 18)
                    pdf.set_text_color(255, 255, 255)
                    pdf.cell(0, 8, 'Cantisa Money - Fiche d\'analyse', ln=True, align='C')
                    pdf.set_font('Helvetica', '', 9)
                    pdf.set_text_color(148, 163, 184)
                    pdf.cell(0, 6, f'Generee le {datetime.now().strftime("%d/%m/%Y %H:%M")}', ln=True, align='C')
                    pdf.ln(8)

                    # ── Identité ─────────────────────────────────────────────
                    pdf.set_text_color(30, 30, 30)
                    pdf.set_font('Helvetica', 'B', 16)
                    pdf.cell(0, 10, stock.get('ticker', ''), ln=True)
                    pdf.set_font('Helvetica', '', 12)
                    pdf.set_text_color(80, 80, 100)
                    pdf.cell(0, 7, stock.get('name', ''), ln=True)
                    pdf.set_font('Helvetica', '', 9)
                    pdf.set_text_color(120, 120, 140)
                    meta_parts = [p for p in [stock.get('sector'), stock.get('industry'), stock.get('country'), stock.get('exchange')] if p]
                    pdf.cell(0, 5, ' / '.join(meta_parts), ln=True)
                    pdf.ln(4)

                    # ── Prix ─────────────────────────────────────────────────
                    pdf.set_font('Helvetica', 'B', 10)
                    pdf.set_text_color(71, 85, 105)
                    pdf.set_fill_color(241, 245, 249)
                    pdf.cell(0, 6, '  PRIX & MARCHE', ln=True, fill=True)
                    pdf.ln(2)
                    cur = stock.get('currency', '')
                    _draw_rows(pdf, [
                        ('Prix actuel',        v(stock.get('current_price'), f' {cur}')),
                        ('Cloture precedente', v(stock.get('previous_close'), f' {cur}')),
                        ('Variation jour',     v(stock.get('day_change_pct'), ' %')),
                        ('52 sem. bas',        v(stock.get('week_52_low'))),
                        ('52 sem. haut',       v(stock.get('week_52_high'))),
                        ('Capitalisation',     v(stock.get('market_cap'), f' {cur}')),
                    ])
                    pdf.ln(4)

                    # ── Valorisation ──────────────────────────────────────────
                    pdf.set_font('Helvetica', 'B', 10)
                    pdf.set_text_color(71, 85, 105)
                    pdf.set_fill_color(241, 245, 249)
                    pdf.cell(0, 6, '  VALORISATION', ln=True, fill=True)
                    pdf.ln(2)
                    _draw_rows_colored(pdf, [
                        ('P/E (trailing)', v(stock.get('pe_trailing')),       rating(None, stock.get('pe_trailing'),  ('min', (15, 25)))),
                        ('P/E (forward)',  v(stock.get('pe_forward')),        rating(None, stock.get('pe_forward'),   ('min', (15, 25)))),
                        ('P/B',           v(stock.get('pb_ratio')),          rating(None, stock.get('pb_ratio'),     ('min', (1, 3)))),
                        ('Dividende',     v(stock.get('dividend_yield'), '%'), (74, 222, 128) if stock.get('dividend_yield') else (150, 150, 150)),
                    ])
                    pdf.ln(4)

                    # ── Rentabilité ───────────────────────────────────────────
                    pdf.set_font('Helvetica', 'B', 10)
                    pdf.set_text_color(71, 85, 105)
                    pdf.set_fill_color(241, 245, 249)
                    pdf.cell(0, 6, '  RENTABILITE', ln=True, fill=True)
                    pdf.ln(2)
                    _draw_rows_colored(pdf, [
                        ('ROE',           v(stock.get('roe'), '%'),              rating(None, stock.get('roe'),              ('max', (15, 5)))),
                        ('ROA',           v(stock.get('roa'), '%'),              rating(None, stock.get('roa'),              ('max', (15, 5)))),
                        ('Marge nette',   v(stock.get('net_margin'), '%'),       rating(None, stock.get('net_margin'),       ('max', (20, 5)))),
                        ('Marge brute',   v(stock.get('gross_margin'), '%'),     rating(None, stock.get('gross_margin'),     ('max', (20, 5)))),
                        ('Marge operat.', v(stock.get('operating_margin'), '%'), rating(None, stock.get('operating_margin'), ('max', (20, 5)))),
                    ])

                    # ── Pied de page ──────────────────────────────────────────
                    pdf.set_y(-14)
                    pdf.set_font('Helvetica', 'I', 7)
                    pdf.set_text_color(180, 180, 190)
                    pdf.cell(0, 5, 'Donnees fournies par Yahoo Finance - A titre informatif, ne constitue pas un conseil en investissement.', align='C')

                buf = io.BytesIO(bytes(pdf.output()))

            except Exception:
                return json_response(traceback.format_exc(), HttpCode.INTERNAL_SERVER_ERROR)

            resp = Response(buf.getvalue())
            resp.headers['Content-Type'] = 'application/pdf'
            resp.headers['Content-Disposition'] = f'attachment; filename="cantisa_analyse_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
            return resp

        # ── Watchlist ─────────────────────────────────────────────────────────

        @app.route(f"{ROUTE_PATH}/watchlist", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def get_watchlist():
            user_id = get_jwt_identity()
            items = Watchlist.query.filter_by(user_id=user_id).order_by(Watchlist.added_at).all()
            result = []
            for item in items:
                try:
                    ticker = yf.Ticker(item.ticker)
                    info = ticker.info
                    if not info or info.get('quoteType') is None:
                        continue
                    dividend_rate = _raw(info.get('dividendRate') or info.get('trailingAnnualDividendRate'))
                    current_price_raw = _raw(info.get('currentPrice') or info.get('regularMarketPrice'))
                    current_price = _safe(current_price_raw)
                    previous_close = _safe(info.get('previousClose'))
                    day_change_pct = None
                    if current_price and previous_close and previous_close != 0:
                        day_change_pct = round((current_price - previous_close) / previous_close * 100, 2)
                    roe = _raw(info.get('returnOnEquity'))
                    net_margin = _raw(info.get('profitMargins'))
                    result.append({
                        'ticker':         item.ticker,
                        'name':           info.get('longName') or info.get('shortName'),
                        'sector':         info.get('sector'),
                        'industry':       info.get('industry'),
                        'country':        info.get('country'),
                        'currency':       info.get('currency'),
                        'exchange':       info.get('exchange'),
                        'current_price':  current_price,
                        'previous_close': previous_close,
                        'day_change_pct': day_change_pct,
                        'week_52_high':   _safe(info.get('fiftyTwoWeekHigh')),
                        'week_52_low':    _safe(info.get('fiftyTwoWeekLow')),
                        'market_cap':     _fmt_market_cap(info.get('marketCap')),
                        'pe_trailing':    _safe(info.get('trailingPE')),
                        'pe_forward':     _safe(info.get('forwardPE')),
                        'pb_ratio':       _safe(info.get('priceToBook')),
                        'dividend_yield': round(dividend_rate / current_price_raw * 100, 2) if dividend_rate and current_price_raw else None,
                        'roe':            round(roe * 100, 2) if roe is not None else None,
                        'roa':            round(_raw(info.get('returnOnAssets')) * 100, 2) if _raw(info.get('returnOnAssets')) is not None else None,
                        'net_margin':     round(net_margin * 100, 2) if net_margin is not None else None,
                        'gross_margin':   round(_raw(info.get('grossMargins')) * 100, 2) if _raw(info.get('grossMargins')) is not None else None,
                        'operating_margin': round(_raw(info.get('operatingMargins')) * 100, 2) if _raw(info.get('operatingMargins')) is not None else None,
                    })
                except Exception:
                    continue
            return json_response(result, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/watchlist", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def add_to_watchlist():
            user_id = get_jwt_identity()
            ticker_symbol = (request.get_json() or {}).get('ticker', '').strip().upper()
            if not ticker_symbol:
                return json_response("Paramètre 'ticker' manquant", HttpCode.BAD_REQUEST)
            existing = Watchlist.query.filter_by(user_id=user_id, ticker=ticker_symbol).first()
            if existing:
                return json_response(f"{ticker_symbol} est déjà dans la watchlist", HttpCode.CONFLICT)
            DB.session.add(Watchlist(user_id=user_id, ticker=ticker_symbol))
            DB.session.commit()
            return json_response(f"{ticker_symbol} ajouté", HttpCode.CREATED)

        @app.route(f"{ROUTE_PATH}/scan/indices", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def get_scan_indices():
            """Retourne les noms d'indices disponibles avec leur nombre de tickers."""
            from sqlalchemy import func
            rows = (DB.session.query(MarketIndex.index_name, func.count(MarketIndex.ticker))
                    .group_by(MarketIndex.index_name)
                    .order_by(MarketIndex.index_name)
                    .all())
            return json_response({name: count for name, count in rows}, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/scan/index-tickers", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def get_index_tickers():
            """Retourne la liste complète des tickers d'un indice donné."""
            name = request.args.get('index', '').strip()
            rows = MarketIndex.query.filter_by(index_name=name).all()
            if not rows:
                return json_response(f"Indice '{name}' inconnu ou vide", HttpCode.NOT_FOUND)
            return json_response([r.ticker for r in rows], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/scan", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def scan_markets():
            body       = request.get_json() or {}
            tickers    = [t.strip().upper() for t in body.get('tickers', []) if t.strip()]
            weights    = body.get('weights', {})
            thresholds = body.get('thresholds', {})
            min_score  = float(body.get('min_score', 0))

            if not tickers:
                return json_response("Liste de tickers vide", HttpCode.BAD_REQUEST)
            if len(tickers) > 600:
                return json_response("Maximum 600 tickers par scan", HttpCode.BAD_REQUEST)

            def fetch_one(sym):
                try:
                    info = yf.Ticker(sym).info
                    if not info or info.get('quoteType') is None:
                        return None
                    dividend_rate    = _raw(info.get('dividendRate') or info.get('trailingAnnualDividendRate'))
                    current_price_r  = _raw(info.get('currentPrice') or info.get('regularMarketPrice'))
                    current_price    = _safe(current_price_r)
                    previous_close   = _safe(info.get('previousClose'))
                    day_change_pct   = None
                    if current_price and previous_close and previous_close != 0:
                        day_change_pct = round((current_price - previous_close) / previous_close * 100, 2)
                    roe              = _raw(info.get('returnOnEquity'))
                    roa              = _raw(info.get('returnOnAssets'))
                    net_margin       = _raw(info.get('profitMargins'))
                    gross_margin     = _raw(info.get('grossMargins'))
                    operating_margin = _raw(info.get('operatingMargins'))

                    stock = {
                        'ticker':           sym,
                        'name':             info.get('longName') or info.get('shortName'),
                        'sector':           info.get('sector'),
                        'industry':         info.get('industry'),
                        'country':          info.get('country'),
                        'currency':         info.get('currency'),
                        'exchange':         info.get('exchange'),
                        'current_price':    current_price,
                        'previous_close':   previous_close,
                        'day_change_pct':   day_change_pct,
                        'week_52_high':     _safe(info.get('fiftyTwoWeekHigh')),
                        'week_52_low':      _safe(info.get('fiftyTwoWeekLow')),
                        'market_cap':       _fmt_market_cap(info.get('marketCap')),
                        'pe_trailing':      _safe(info.get('trailingPE')),
                        'pe_forward':       _safe(info.get('forwardPE')),
                        'pb_ratio':         _safe(info.get('priceToBook')),
                        'dividend_yield':   round(dividend_rate / current_price_r * 100, 2) if dividend_rate and current_price_r else None,
                        'roe':              round(roe * 100, 2) if roe is not None else None,
                        'roa':             round(roa * 100, 2) if roa is not None else None,
                        'net_margin':       round(net_margin * 100, 2) if net_margin is not None else None,
                        'gross_margin':     round(gross_margin * 100, 2) if gross_margin is not None else None,
                        'operating_margin': round(operating_margin * 100, 2) if operating_margin is not None else None,
                    }
                    stock['score'] = _compute_score(stock, weights, thresholds)
                    return stock
                except Exception:
                    return None

            results = []
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = {pool.submit(fetch_one, t): t for t in tickers}
                for future in as_completed(futures):
                    data = future.result()
                    if data and (data['score'] is None or data['score'] >= min_score):
                        results.append(data)

            results.sort(key=lambda s: (s['score'] is None, -(s['score'] or 0)))
            return json_response(results, HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/watchlist/<string:ticker>", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, MARKETS_PERM)
        def remove_from_watchlist(ticker):
            user_id = get_jwt_identity()
            item = Watchlist.query.filter_by(user_id=user_id, ticker=ticker.upper()).first()
            if not item:
                return json_response("Ticker non trouvé dans la watchlist", HttpCode.NOT_FOUND)
            DB.session.delete(item)
            DB.session.commit()
            return json_response(f"{ticker} retiré", HttpCode.OK)


def _draw_rows(pdf, rows):
    """Lignes label / valeur sans coloration."""
    col_w = [80, 100]
    for i, (label, val) in enumerate(rows):
        row_bg = (248, 250, 252) if i % 2 == 0 else (255, 255, 255)
        pdf.set_fill_color(*row_bg)
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(col_w[0], 6, f'  {label}', fill=True)
        pdf.set_text_color(30, 30, 50)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(col_w[1], 6, val, fill=True, ln=True)


def _draw_rows_colored(pdf, rows):
    """Lignes label / valeur avec carré coloré selon performance.
    Utilise rect() au lieu de circle() pour compatibilité fpdf2."""
    col_w_label = 80
    col_w_val   = 100
    row_h       = 6

    for i, (label, val, color) in enumerate(rows):
        row_bg = (248, 250, 252) if i % 2 == 0 else (255, 255, 255)

        # Fond de ligne complet
        x0, y0 = pdf.get_x(), pdf.get_y()
        pdf.set_fill_color(*row_bg)
        pdf.rect(x0, y0, col_w_label + col_w_val, row_h, 'F')

        # Label
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(100, 116, 139)
        pdf.cell(col_w_label, row_h, f'  {label}', fill=False)

        # Carré coloré (4×4 mm, centré verticalement dans la ligne)
        sq = 3
        pdf.set_fill_color(*color)
        pdf.rect(pdf.get_x() + 1, y0 + (row_h - sq) / 2, sq, sq, 'F')

        # Valeur
        pdf.set_fill_color(*row_bg)
        pdf.set_text_color(30, 30, 50)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(col_w_val, row_h, f'   {val}', fill=False, ln=True)
