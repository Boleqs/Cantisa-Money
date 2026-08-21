import uuid
from decimal import Decimal, ROUND_DOWN

from backend.config import HttpCode
from backend.utils.api_responses import json_response
from backend.utils.market_price import fetch_live_price, convert_amount, get_fx_rate


def resolve_current_value(symbol, target_currency, FxRates):
    """Récupère le prix de marché actuel du ticker et le convertit vers target_currency.
    Retourne (value_per_unit, error_response) — error_response est None si succès."""
    result = fetch_live_price(symbol)
    if not result['valid']:
        return None, json_response(result['error'], HttpCode.BAD_REQUEST)
    if result['price'] is None:
        return None, json_response(f"Prix indisponible pour '{symbol}'", HttpCode.BAD_REQUEST)

    value_per_unit = convert_amount(result['price'], result['currency'], target_currency, FxRates)
    if value_per_unit is None:
        return None, json_response(
            f"Taux de change {result['currency']} → {target_currency} indisponible", HttpCode.BAD_REQUEST)
    return value_per_unit, None


def resolve_purchase_price(symbol, target_currency, purchase_price_native, purchase_date, FxRates):
    """Convertit un prix d'achat natif (devise du ticker) au taux historique de purchase_date.
    Retourne (purchase_price, error_response) — error_response est None si succès."""
    result = fetch_live_price(symbol)
    if not result['valid']:
        return None, json_response(result['error'], HttpCode.BAD_REQUEST)

    purchase_price = convert_amount(purchase_price_native, result['currency'], target_currency, FxRates, on_date=purchase_date)
    if purchase_price is None:
        return None, json_response(
            f"Taux de change historique {result['currency']} → {target_currency} indisponible pour la date d'achat",
            HttpCode.BAD_REQUEST)
    return purchase_price, None


def resolve_split_amounts(Accounts, Commodities, dest_account, source_account, total_cost, cost_currency, purchase_date, FxRates):
    """Convertit total_cost (exprimé dans cost_currency) vers la devise propre de chaque compte
    (chaque compte reçoit un montant dans sa propre devise, cf. rt_transactions.py). Retourne
    (dest_amount, source_amount, dest_fx_rate, error_response). La transaction générée est dans la
    devise du compte source (cf. add_possession) : dest_fx_rate permet de reconvertir dest_amount
    vers cette devise (Splits.fx_rate, même convention que rt_transactions.py)."""
    dest_commodity = Commodities.query.filter_by(id=dest_account.currency_id).first()
    dest_code = dest_commodity.short_name if dest_commodity else cost_currency
    dest_amount = convert_amount(total_cost, cost_currency, dest_code, FxRates, on_date=purchase_date)
    if dest_amount is None:
        return None, None, None, json_response(
            f"Taux de change historique {cost_currency} → {dest_code} indisponible", HttpCode.BAD_REQUEST)

    source_commodity = Commodities.query.filter_by(id=source_account.currency_id).first()
    source_code = source_commodity.short_name if source_commodity else cost_currency
    source_amount = convert_amount(total_cost, cost_currency, source_code, FxRates, on_date=purchase_date)
    if source_amount is None:
        return None, None, None, json_response(
            f"Taux de change historique {cost_currency} → {source_code} indisponible", HttpCode.BAD_REQUEST)

    dest_fx_rate = get_fx_rate(dest_code, source_code, FxRates, on_date=purchase_date) or 1.0

    return dest_amount, source_amount, dest_fx_rate, None


def convert_asset_to_default_currency(amount, asset_currency, default_currency, manual_fx_rate, on_date, FxRates):
    """Convertit un montant depuis la devise native de l'actif vers la devise par défaut de
    l'utilisateur (Settings.currency) — au taux manuel si fourni (1 unité de asset_currency =
    manual_fx_rate unité(s) de default_currency), sinon au taux historique automatique de on_date.
    Le taux manuel cible toujours cette paire (actif → défaut), indépendamment du compte réellement
    débité/crédité : la jambe compte réel se résout ensuite automatiquement à partir de la devise
    par défaut (cf. resolve_split_amounts), un pas qui reste fiable même quand la devise de l'actif
    est trop exotique pour avoir un historique de change disponible. Retourne (amount_in_default,
    resolved_rate, error_response) — resolved_rate est le taux effectivement appliqué (manuel ou
    résolu automatiquement, 1.0 si les devises sont identiques) : à persister par l'appelant
    (AssetPossession.fx_rate / AssetDisposal.fx_rate) pour ne plus jamais redépendre d'une
    résolution automatique implicite a posteriori (ex: taux historique qui aurait changé entre
    l'achat et une vente ultérieure du même lot)."""
    if asset_currency == default_currency:
        return amount, 1.0, None
    if manual_fx_rate is not None:
        rate = float(manual_fx_rate)
        return amount * rate, rate, None
    rate = get_fx_rate(asset_currency, default_currency, FxRates, on_date=on_date)
    if rate is None:
        return None, None, json_response(
            f"Taux de change historique {asset_currency} → {default_currency} indisponible — renseigne un taux manuel",
            HttpCode.BAD_REQUEST)
    return amount * rate, rate, None


def convert_default_to_asset_currency(amount, asset_currency, default_currency, manual_fx_rate, on_date, FxRates):
    """Inverse de convert_asset_to_default_currency — reconvertit un montant saisi en devise par
    défaut (les frais, toujours saisis dans cette devise) vers la devise native de l'actif, pour
    les calculs qui doivent y rester exprimés (prix d'achat/vente, plus-value réalisée — cf.
    rt_tax.py qui reconvertit lui-même depuis commodity.short_name). Retourne (amount_in_asset,
    error_response)."""
    if asset_currency == default_currency or amount == 0:
        return amount, None
    if manual_fx_rate is not None:
        return amount / float(manual_fx_rate), None
    converted = convert_amount(amount, default_currency, asset_currency, FxRates, on_date=on_date)
    if converted is None:
        return None, json_response(
            f"Taux de change historique {default_currency} → {asset_currency} indisponible", HttpCode.BAD_REQUEST)
    return converted, None


def format_qty(q):
    """Rendu compact d'une quantité potentiellement fractionnaire dans une description de
    transaction (ex: "x2.29" plutôt que "x2.290000")."""
    s = f"{float(q):.6f}".rstrip('0').rstrip('.')
    return s or '0'


def resolve_dca_unit_price(asset, commodity, FxRates):
    """Prix d'exécution d'un achat DCA : le prix de marché COURANT (pas historique, contrairement à
    resolve_purchase_price qui reconstitue le taux historique pour une saisie manuelle a
    posteriori). Un DCA achète "au prix du marché à l'instant T", jamais rétroactivement — même pour
    un rattrapage d'échéances en retard — ce qui évite de multiplier les appels yfinance historiques
    dans la passe horaire du scheduler. Actif non suivi en live : value_per_unit sert de prix (déjà
    dans la devise de commodity, native = convertie). Retourne (converted_price, native_price,
    error_message|None)."""
    if not asset.track_live_price:
        v = float(asset.value_per_unit or 0)
        return v, v, None
    result = fetch_live_price(asset.symbol)
    if not result['valid'] or result['price'] is None:
        return None, None, result.get('error') or f"Prix indisponible pour '{asset.symbol}'"
    converted = convert_amount(result['price'], result['currency'], commodity.short_name, FxRates)
    if converted is None:
        return None, None, f"Taux de change {result['currency']} → {commodity.short_name} indisponible"
    return converted, result['price'], None


def compute_dca_quantity(amount, source_currency_code, commodity_code, unit_price_converted, FxRates):
    """amount est dans la devise du compte source (même convention que Subscriptions.amount).
    Converti dans la devise de l'actif avant division par le prix unitaire. Arrondi vers le bas
    (ROUND_DOWN) à 6 décimales : ne jamais dépenser plus que `amount` à cause d'un arrondi — le
    coût réel (quantity * unit_price) est systématiquement <= amount, le reliquat non dépensé n'est
    pas reporté (comportement standard d'un DCA chez un courtier réel). Retourne
    (quantity: Decimal|None, error_message|None)."""
    amount_in_asset_currency = convert_amount(float(amount), source_currency_code, commodity_code, FxRates)
    if amount_in_asset_currency is None:
        return None, f"Taux de change {source_currency_code} → {commodity_code} indisponible"
    if not unit_price_converted or unit_price_converted <= 0:
        return None, "Prix unitaire de l'actif invalide (0 ou négatif)"
    quantity = (Decimal(str(amount_in_asset_currency)) / Decimal(str(unit_price_converted))).quantize(
        Decimal('0.000001'), rounding=ROUND_DOWN)
    if quantity <= 0:
        return None, "Montant trop faible pour acheter une quantité non nulle au prix actuel"
    return quantity, None


def create_possession_lot(DB, Transactions, Splits, AssetPossession, user_id, asset, dest_account,
                           source_account, quantity, purchase_price, purchase_price_native,
                           purchase_date, description, dest_amount, source_amount, dest_fx_rate,
                           dca_plan_id=None):
    """Cœur commun à add_possession et à l'exécution DCA : écrit la Transaction + 2 Splits (si
    source_account fourni) puis le lot AssetPossession. Ne fait NI résolution de prix NI calcul des
    montants convertis (restent la responsabilité de l'appelant, qui seul connaît le contexte :
    saisie manuelle vs. calcul DCA) — factorise uniquement l'écriture en base. Ne commit PAS (au
    caller de committer)."""
    tx = None
    source_split_id = dest_split_id = None
    if source_account:
        tx = Transactions(
            user_id=user_id, currency_id=source_account.currency_id,
            post_date=purchase_date, effective_date=purchase_date,
            description=description, category_id=None, is_cleared=True)
        DB.session.add(tx)
        DB.session.flush()
        source_split_id, dest_split_id = uuid.uuid4(), uuid.uuid4()
        DB.session.add(Splits(id=source_split_id, tx_id=tx.id, account_id=source_account.id, quantity=-source_amount, fx_rate=1.0))
        DB.session.add(Splits(id=dest_split_id, tx_id=tx.id, account_id=dest_account.id, quantity=dest_amount, fx_rate=dest_fx_rate))
        DB.session.flush()

    p = AssetPossession(
        user_id=user_id, asset_id=asset.id, account_id=dest_account.id,
        source_account_id=source_account.id if source_account else None,
        tx_id=tx.id if tx else None, source_split_id=source_split_id, dest_split_id=dest_split_id,
        quantity=quantity, purchase_price=purchase_price, purchase_price_native=purchase_price_native,
        purchase_date=purchase_date, dca_plan_id=dca_plan_id)
    DB.session.add(p)
    return p
