from datetime import date, datetime

# Au-delà, on ne fait plus confiance aux stats comparatives ("X% sous votre moyenne", streak de
# budgets sans dépassement...) — pas un réglage de cadence d'import par utilisateur : soit il y a
# assez de données récentes pour qu'une comparaison ait un sens, soit non.
STALE_THRESHOLD_HOURS = 48


def compute_freshness(user_id, Transactions):
    """Fraîcheur du grand livre d'un utilisateur, pour décider si les stats "de ce mois-ci" ou
    comparatives sont dignes de confiance. `stale` si l'une des deux conditions est vraie :
    - dernière transaction connue à plus de STALE_THRESHOLD_HOURS ;
    - aucune transaction dont post_date tombe dans le mois civil en cours (même si la dernière
      transaction globale est récente, un mois en cours sans transaction propre ne permet pas de
      calculer une stat "de ce mois-ci" fiable — cas d'un import qui saute carrément un mois)."""
    last = Transactions.query.filter_by(user_id=user_id).order_by(Transactions.post_date.desc()).first()
    if not last:
        return {'stale': False, 'last_transaction_date': None, 'days_since': None}

    hours_since = (datetime.now() - last.post_date).total_seconds() / 3600
    month_start = date.today().replace(day=1)
    has_current_month_tx = Transactions.query.filter(
        Transactions.user_id == user_id,
        Transactions.post_date >= month_start,
    ).first() is not None

    return {
        'stale': hours_since > STALE_THRESHOLD_HOURS or not has_current_month_tx,
        'last_transaction_date': last.post_date.date().isoformat(),
        'days_since': (date.today() - last.post_date.date()).days,
    }
