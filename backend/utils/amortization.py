import math

from backend.utils.recurrence import next_occurrence


def monthly_rate(annual_rate_pct):
    """3.45 (%) -> 0.002875 (taux mensuel)."""
    return (annual_rate_pct / 100) / 12


def compute_installment_payment(principal, annual_rate_pct, term_months):
    """Mensualité constante (capital+intérêts) à l'amortissement français. Taux nul -> amortissement
    linéaire (principal / term_months, pas d'intérêts)."""
    r = monthly_rate(annual_rate_pct)
    if r == 0:
        return principal / term_months
    return principal * r / (1 - (1 + r) ** -term_months)


def solve_term_for_payment(principal, annual_rate_pct, target_payment):
    """Inverse de compute_installment_payment : plus petit nombre entier de mensualités (arrondi
    au mois supérieur) nécessaire pour amortir `principal` avec une mensualité constante de
    `target_payment` au taux annuel `annual_rate_pct`. Retourne None si `target_payment` ne couvre
    même pas les intérêts de la première période (le capital ne diminuerait jamais)."""
    r = monthly_rate(annual_rate_pct)
    if r == 0:
        if target_payment <= 0:
            return None
        return math.ceil(principal / target_payment)

    first_period_interest = principal * r
    if target_payment <= first_period_interest:
        return None
    n = -math.log(1 - r * principal / target_payment) / math.log(1 + r)
    return math.ceil(n)


def build_schedule(principal, annual_rate_pct, term_months, first_due_date, payment_day,
                    insurance_monthly_amount=0, first_installment_number=1, payment_override=None):
    """Génère `term_months` échéances à partir de `first_due_date` (date d'échéance de la première
    ligne elle-même), les suivantes calculées via next_occurrence('monthly', ...) pour respecter le
    clampage de fin de mois déjà utilisé par les abonnements. Le résidu d'arrondi cumulé est absorbé
    dans le principal_portion de la DERNIÈRE échéance, pour que remaining_principal_after y soit
    exactement 0 et que la somme des principal_portion égale exactement `principal`.

    `payment_override` : si fourni, utilisé tel quel comme mensualité capital+intérêts au lieu de la
    recalculer via compute_installment_payment — utilisé par le mode 'keep_payment' d'une révision de
    taux pour conserver la mensualité exacte plutôt qu'une valeur legèrement différente due à
    l'arrondi du nombre d'échéances au mois supérieur.

    Retourne une liste de dicts prêts à instancier LoanInstallments(loan_id=..., **row)."""
    payment = payment_override if payment_override is not None else \
        compute_installment_payment(principal, annual_rate_pct, term_months)
    r = monthly_rate(annual_rate_pct)

    rows = []
    remaining = float(principal)
    due_date = first_due_date
    for i in range(term_months):
        installment_number = first_installment_number + i
        is_last = (i == term_months - 1)

        interest_portion = round(remaining * r, 2) if r else 0.0
        if is_last:
            principal_portion = round(remaining, 2)
        else:
            principal_portion = round(payment - interest_portion, 2)
        remaining -= principal_portion
        insurance_portion = round(float(insurance_monthly_amount or 0), 2)
        total_amount = round(principal_portion + interest_portion + insurance_portion, 2)

        rows.append({
            'installment_number': installment_number,
            'due_date': due_date,
            'principal_portion': principal_portion,
            'interest_portion': interest_portion,
            'insurance_portion': insurance_portion,
            'total_amount': total_amount,
            'remaining_principal_after': round(remaining, 2) if not is_last else 0.0,
        })

        if not is_last:
            due_date = next_occurrence('monthly', payment_day, None, None, due_date)

    return rows


def regenerate_from_revision(base_remaining_principal, new_annual_rate_pct, recalc_mode, effective_date,
                              payment_day, current_installment_count, current_total_payment,
                              first_installment_number, insurance_monthly_amount=0):
    """Calcule le nouvel échéancier (liste de dicts, même format que build_schedule) applicable à
    partir de `effective_date`, suite à une révision de taux. La route appelante possède la lecture/
    suppression/insertion en DB ; cette fonction est un calcul pur.

    - recalc_mode == 'keep_term'    : conserve le nombre d'échéances restantes (`current_installment_count`),
      recalcule la mensualité au nouveau taux.
    - recalc_mode == 'keep_payment' : conserve la mensualité capital+intérêts actuelle (`current_total_payment`,
      hors assurance), recalcule le nombre d'échéances nécessaires au nouveau taux.

    Lève ValueError si `current_total_payment` ne couvre plus les intérêts au nouveau taux
    (mode keep_payment) — erreur métier à renvoyer en 400 par la route."""
    if recalc_mode == 'keep_term':
        term_months = current_installment_count
    elif recalc_mode == 'keep_payment':
        term_months = solve_term_for_payment(base_remaining_principal, new_annual_rate_pct, current_total_payment)
        if term_months is None:
            raise ValueError(
                "Mensualité insuffisante pour couvrir les intérêts au nouveau taux — "
                "augmentez la mensualité ou choisissez 'garder la durée'.")
    else:
        raise ValueError(f"recalc_mode invalide : {recalc_mode}")

    payment_override = current_total_payment if recalc_mode == 'keep_payment' else None
    return build_schedule(
        base_remaining_principal, new_annual_rate_pct, term_months, effective_date, payment_day,
        insurance_monthly_amount, first_installment_number, payment_override=payment_override,
    )
