import calendar
from datetime import date, timedelta

from backend.utils.market_price import convert_amount
from backend.utils.wealth import compute_bank_net_worth, get_portfolio_breakdown, _portfolio_account_ids
from backend.utils.recurrence import next_occurrence

# Types d'actifs "financiers" (marché, forte volatilité mais fort potentiel long terme) vs
# "physiques" (immobilier/véhicule, appréciation plus lente et plus stable) — deux taux de
# croissance distincts plutôt qu'un seul taux global, cf. décision explicite de l'utilisateur.
FINANCIAL_ASSET_TYPES = ('Stock', 'ETF')

CASH_ACCOUNT_TYPES = ('Current', 'Assets', 'Equity')


def _add_months(d, n):
    month = d.month - 1 + n
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _account_currency(account, commodities_by_id, target_currency):
    commodity = commodities_by_id.get(account.currency_id)
    return commodity.short_name if commodity else target_currency


def _excluded_transaction_ids(Loans, LoanInstallments, Transactions, Subscriptions, AssetPossession, user_id, start, today):
    """Transactions déjà couvertes par une projection explicite (échéances de crédit, exécutions
    d'abonnement, contributions DCA) — à exclure de toute moyenne historique pour éviter un double
    comptage dans project_wealth(). Exclusion au niveau de la TRANSACTION (jamais du compte entier) :
    un compte "Dépenses courantes" fourre-tout, alimenté à la fois par des abonnements et des
    dépenses ponctuelles, ne doit perdre que la part abonnements/crédits/DCA, pas être ignoré en
    bloc."""
    excluded_tx_ids = set()
    for loan in Loans.query.filter_by(user_id=user_id, is_closed=False).all():
        paid_insts = LoanInstallments.query.filter(
            LoanInstallments.loan_id == loan.id,
            LoanInstallments.transaction_id.isnot(None),
            LoanInstallments.due_date >= start,
            LoanInstallments.due_date <= today,
        ).all()
        excluded_tx_ids.update(i.transaction_id for i in paid_insts)

    # Les transactions générées par un abonnement portent sa description exacte (voir
    # scheduler.py::_execute_subscription, description=sub.name) — heuristique fiable en pratique
    # (un nom d'abonnement dupliqué par coïncidence dans une description manuelle est rare) plutôt
    # que d'exiger un lien explicite qui n'existe pas dans le modèle Subscriptions.
    sub_names = [s.name for s in Subscriptions.query.filter_by(user_id=user_id).all()]
    if sub_names:
        sub_tx_ids = Transactions.query.filter(
            Transactions.user_id == user_id,
            Transactions.description.in_(sub_names),
            Transactions.post_date >= start,
            Transactions.post_date <= today,
        ).with_entities(Transactions.id).all()
        excluded_tx_ids.update(tx_id for (tx_id,) in sub_tx_ids)

    # Contributions DCA : lien explicite via dca_plan_id (plus robuste que le matching par nom des
    # abonnements ci-dessus, la description varie à chaque exécution — voir scheduler.py::
    # _execute_dca_contribution). Sans cette exclusion, chaque sortie DCA historique serait comptée
    # deux fois : une fois ici (comme dépense "organique") et une fois dans la boucle DCA future de
    # project_wealth() — même bug que celui déjà évité pour abonnements/crédits.
    dca_tx_ids = AssetPossession.query.filter(
        AssetPossession.user_id == user_id,
        AssetPossession.dca_plan_id.isnot(None),
        AssetPossession.tx_id.isnot(None),
        AssetPossession.purchase_date >= start,
        AssetPossession.purchase_date <= today,
    ).with_entities(AssetPossession.tx_id).all()
    excluded_tx_ids.update(tx_id for (tx_id,) in dca_tx_ids)
    return excluded_tx_ids


def compute_avg_monthly_net_flow(DB, Accounts, Transactions, Splits, AssetPossession, Loans, LoanInstallments,
                                  Subscriptions, Commodities, FxRates, user_id, target_currency):
    """Variation mensuelle moyenne du pool bancaire (Current/Assets/Equity, hors comptes-conteneurs
    de portefeuille) sur les 12 derniers mois ("période équivalente de l'année précédente"), hors
    transactions déjà couvertes par une projection explicite (abonnements, échéances de crédit).

    Volontairement un flux NET (peut être positif = épargne, négatif = déficit) et non une simple
    moyenne de dépenses : le salaire n'est presque jamais modélisé comme un Abonnement dans cette
    appli (entré manuellement chaque mois, comme un loyer) — ignorer les revenus historiques
    ferait fondre le solde bancaire projeté indéfiniment pour n'importe quel utilisateur réel, ce
    qui rendrait la projection inutilisable. Ce flux net capture salaire, dépenses ponctuelles,
    loyer manuel, etc. en un seul chiffre, sans exiger que le revenu soit catégorisé."""
    today = date.today()
    start = today - timedelta(days=365)
    excluded_tx_ids = _excluded_transaction_ids(Loans, LoanInstallments, Transactions, Subscriptions, AssetPossession, user_id, start, today)

    bank_accounts = Accounts.query.filter(
        Accounts.user_id == user_id,
        Accounts.account_type.in_(CASH_ACCOUNT_TYPES),
        Accounts.is_virtual == False,
        Accounts.is_hidden == False,
        ~Accounts.id.in_(_portfolio_account_ids(AssetPossession, user_id)),
    ).all()
    if not bank_accounts:
        return 0.0

    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}
    accounts_by_id = {a.id: a for a in bank_accounts}
    account_ids = list(accounts_by_id.keys())

    query = DB.session.query(Splits.account_id, Splits.quantity).join(
        Transactions, Splits.tx_id == Transactions.id
    ).filter(
        Transactions.user_id == user_id,
        Splits.account_id.in_(account_ids),
        Transactions.post_date >= start,
        Transactions.post_date <= today,
    )
    if excluded_tx_ids:
        query = query.filter(~Splits.tx_id.in_(excluded_tx_ids))

    total = 0.0
    for account_id, quantity in query.all():
        code = _account_currency(accounts_by_id[account_id], commodities_by_id, target_currency)
        total += convert_amount(float(quantity), code, target_currency, FxRates) or 0

    return round(total / 12, 2)


def _goal_occurrences(goal, today, horizon_end):
    """Dates (dans l'horizon, à partir d'aujourd'hui) où un objectif retire de la trésorerie
    projetée : une seule fois pour 'one_time', chaque mois de target_date à end_date (ou la fin de
    l'horizon si end_date est vide — objectif "jusqu'à la fin de la simulation", ex. train de vie
    de retraite) pour 'recurring'."""
    target = goal['target_date']
    if goal['goal_type'] == 'one_time':
        return [target] if today <= target <= horizon_end else []
    end = min(goal['end_date'], horizon_end) if goal.get('end_date') else horizon_end
    occs = []
    k = 0
    d = target
    while d <= end:
        if d >= today:
            occs.append(d)
        k += 1
        d = _add_months(target, k)
    return occs


def project_wealth(DB, Accounts, Assets, AssetPossession, AssetDisposal, Commodities, FxRates,
                    Loans, LoanInstallments, Subscriptions, DcaPlans, Transactions, Splits, user_id,
                    horizon_months, growth_financial_pct, growth_physical_pct, growth_cash_pct,
                    avg_monthly_net_flow_override, target_currency, goals=None,
                    invest_mode='amount', invest_financial_amount=0.0, invest_physical_amount=0.0,
                    invest_financial_pct=0.0, invest_physical_pct=0.0):
    today = date.today()
    commodities_by_id = {c.id: c for c in Commodities.query.filter_by(user_id=user_id).all()}
    assets_by_id = {a.id: a for a in Assets.query.filter_by(user_id=user_id).all()}

    bank_cash = compute_bank_net_worth(Accounts, Commodities, AssetPossession, FxRates, user_id, target_currency)
    portfolio = get_portfolio_breakdown(Assets, AssetPossession, AssetDisposal, Commodities, FxRates, user_id, target_currency)
    portfolio_financial = sum(a['value'] for a in portfolio if a['asset_type'] in FINANCIAL_ASSET_TYPES)
    portfolio_physical = sum(a['value'] for a in portfolio if a['asset_type'] not in FINANCIAL_ASSET_TYPES)

    if avg_monthly_net_flow_override is not None:
        avg_monthly_net_flow = avg_monthly_net_flow_override
        net_flow_auto = False
    else:
        avg_monthly_net_flow = compute_avg_monthly_net_flow(
            DB, Accounts, Transactions, Splits, AssetPossession, Loans, LoanInstallments, Subscriptions,
            Commodities, FxRates, user_id, target_currency)
        net_flow_auto = True

    # Part du flux mensuel moyen affectée à l'investissement plutôt qu'à la trésorerie — deux modes :
    # montant fixe (indépendant du flux) ou pourcentage DU flux (recalculé ici une fois le flux
    # résolu, auto ou manuel, pour éviter au frontend de connaître la valeur auto avant le 1er appel).
    if invest_mode == 'percent':
        invest_financial = avg_monthly_net_flow * invest_financial_pct / 100
        invest_physical = avg_monthly_net_flow * invest_physical_pct / 100
    else:
        invest_financial = invest_financial_amount
        invest_physical = invest_physical_amount

    # Crédits en cours : l'échéancier complet (jusqu'au terme) est déjà généré et stocké à la
    # création du prêt (build_schedule(), voir rt_loans.py) — aucune amortization à recalculer ici,
    # juste à lire les échéances déjà en base.
    active_loans = Loans.query.filter_by(user_id=user_id, is_closed=False).all()
    loan_currency = {}
    loan_installments = {}
    liability_start = {}
    for loan in active_loans:
        liability_account = Accounts.query.get(loan.liability_account_id)
        loan_currency[loan.id] = _account_currency(liability_account, commodities_by_id, target_currency) if liability_account else target_currency
        insts = LoanInstallments.query.filter_by(loan_id=loan.id).order_by(LoanInstallments.due_date).all()
        loan_installments[loan.id] = insts
        past = [i for i in insts if i.due_date <= today]
        liability_start[loan.id] = float(past[-1].remaining_principal_after) if past else float(loan.principal)

    horizon_end = _add_months(today, horizon_months)

    # Abonnements : occurrences futures énumérées via next_occurrence() (pas de vue "plage" toute
    # faite côté backend — seule la prochaine occurrence après une date existe, voir recurrence.py).
    subscriptions = Subscriptions.query.filter_by(user_id=user_id).all()
    accounts_by_id = {a.id: a for a in Accounts.query.filter_by(user_id=user_id).all()}
    sub_occurrences = {}
    for s in subscriptions:
        occs = []
        d = next_occurrence(s.schedule_type, s.day_of_month, s.month_of_year, s.weekdays, today)
        while d <= horizon_end:
            occs.append(d)
            d = next_occurrence(s.schedule_type, s.day_of_month, s.month_of_year, s.weekdays, d)
        sub_occurrences[s.id] = occs

    # Plans DCA : seules les occurrences FUTURES (depuis aujourd'hui) sont énumérées — les
    # contributions déjà exécutées sont de vrais lots AssetPossession, déjà comptés dans
    # portfolio_financial/portfolio_physical au départ via get_portfolio_breakdown ci-dessus ; les
    # ré-énumérer ici doublerait leur effet.
    dca_plans = DcaPlans.query.filter_by(user_id=user_id).all()
    dca_occurrences = {}
    for plan in dca_plans:
        occs = []
        anchor = today if today >= plan.start_date else (plan.start_date - timedelta(days=1))
        d = next_occurrence(plan.schedule_type, plan.day_of_month, plan.month_of_year, plan.weekdays, anchor)
        while d <= horizon_end and (plan.end_date is None or d <= plan.end_date):
            occs.append(d)
            d = next_occurrence(plan.schedule_type, plan.day_of_month, plan.month_of_year, plan.weekdays, d)
        dca_occurrences[plan.id] = occs

    # Objectifs de vie (Lifetime Planner) : trajectoire de trésorerie parallèle à bank_cash, qui
    # subit en plus les retraits de chaque objectif — voir _goal_occurrences(). goal_balances
    # trace, pour chaque objectif, la trésorerie-avec-objectifs à chaque mois où il retire de
    # l'argent, pour déterminer après coup s'il reste couvert (jamais négatif).
    goals = goals or []
    has_goals = bool(goals)
    goal_occurrences = {g['id']: _goal_occurrences(g, today, horizon_end) for g in goals}
    goal_balances = {g['id']: [] for g in goals}
    bank_cash_goals = bank_cash if has_goals else None

    r_fin = (1 + growth_financial_pct / 100) ** (1 / 12) - 1
    r_phys = (1 + growth_physical_pct / 100) ** (1 / 12) - 1
    r_cash = (1 + growth_cash_pct / 100) ** (1 / 12) - 1

    # liability_start est dans la devise propre à chaque prêt (potentiellement différente entre
    # prêts, et de target_currency) — conversion avant sommation.
    liabilities_start = sum(
        convert_amount(v, loan_currency[loan_id], target_currency, FxRates) or 0
        for loan_id, v in liability_start.items()
    )

    # financial_net_worth = portefeuille - crédits, SANS la trésorerie bancaire — même périmètre
    # que "Patrimoine financier net" sur /patrimoine (WealthOverview.vue, voir compute_bank_net_worth
    # et son commentaire "hors soldes bancaires, voir Rapports prédéfinis pour le patrimoine total").
    # bank_cash reste simulé et exposé à part (trésorerie projetée) mais ne doit jamais être mélangé
    # dans ce chiffre, sous peine d'afficher deux valeurs différentes pour "le même" patrimoine net
    # entre /patrimoine et /patrimoine/prediction — bug remonté par l'utilisateur le 2026-07-25.
    points = [{
        'date': today.isoformat(),
        'bank_cash': round(bank_cash, 2),
        'bank_cash_with_goals': round(bank_cash_goals, 2) if has_goals else None,
        'portfolio_value': round(portfolio_financial + portfolio_physical, 2),
        'liabilities': round(liabilities_start, 2),
        'financial_net_worth': round(portfolio_financial + portfolio_physical - liabilities_start, 2),
    }]

    cur_date = today
    for m in range(1, horizon_months + 1):
        next_date = _add_months(today, m)

        portfolio_financial *= (1 + r_fin)
        portfolio_physical *= (1 + r_phys)
        # L'épargne accumulée (bank_cash) doit elle aussi composer, sinon la trajectoire du
        # patrimoine reste quasi linéaire sur un long horizon (seul le portefeuille croît, alors
        # que l'essentiel de la variation vient souvent du cash accumulé mois après mois) — voir
        # retour utilisateur du 2026-07-25 ("se base sur le capital de départ, ne prend pas en
        # compte les intérêts composés"). bank_cash_goals compose sur SA propre valeur (donc moins
        # vite qu'un simple décalage de bank_cash) une fois amputée par des objectifs.
        bank_cash *= (1 + r_cash)
        if has_goals:
            bank_cash_goals *= (1 + r_cash)

        # Delta commun aux deux trajectoires (abonnements, flux net, échéances de crédit) : montant
        # en dollars, identique que la trésorerie porte des objectifs ou non — seuls les retraits
        # d'objectifs, appliqués plus bas, divergent entre bank_cash et bank_cash_goals.
        month_delta = 0.0

        for s in subscriptions:
            occs_in_month = [o for o in sub_occurrences[s.id] if cur_date < o <= next_date]
            if not occs_in_month:
                continue
            from_acc = accounts_by_id.get(s.from_account_id)
            to_acc = accounts_by_id.get(s.to_account_id)
            from_is_cash = from_acc and from_acc.account_type in CASH_ACCOUNT_TYPES
            to_is_cash = to_acc and to_acc.account_type in CASH_ACCOUNT_TYPES
            if from_is_cash == to_is_cash:
                continue  # virement interne (net nul sur le pool bancaire) ou hors pool bancaire des deux côtés
            code = _account_currency(from_acc if from_is_cash else to_acc, commodities_by_id, target_currency)
            amount = (convert_amount(float(s.amount), code, target_currency, FxRates) or 0) * len(occs_in_month)
            month_delta += amount if to_is_cash else -amount

        # Contributions DCA de ce mois : sortent du pool bancaire (comme une souscription vers un
        # compte non-cash) et alimentent la croissance composée du portefeuille — mais seulement à
        # partir du mois SUIVANT (cette boucle tourne après portfolio_financial/physical *= (1+r)
        # ci-dessus, donc une contribution de ce mois ne compose pas rétroactivement pour ce mois).
        for plan in dca_plans:
            occs_in_month = [o for o in dca_occurrences.get(plan.id, []) if cur_date < o <= next_date]
            if not occs_in_month:
                continue
            source_acc = accounts_by_id.get(plan.source_account_id)
            if not source_acc:
                continue
            code = _account_currency(source_acc, commodities_by_id, target_currency)
            contribution_amount = (convert_amount(float(plan.amount), code, target_currency, FxRates) or 0) * len(occs_in_month)
            month_delta -= contribution_amount

            asset = assets_by_id.get(plan.asset_id)
            if asset:
                if asset.asset_type in FINANCIAL_ASSET_TYPES:
                    portfolio_financial += contribution_amount
                else:
                    portfolio_physical += contribution_amount

        # Part du flux investie chaque mois : sort de la trésorerie projetée comme une contribution
        # DCA, et compose sur le portefeuille à partir du mois suivant (ajoutée après la
        # multiplication par (1+r) ci-dessus, même convention que les contributions DCA).
        month_delta += avg_monthly_net_flow - invest_financial - invest_physical
        portfolio_financial += invest_financial
        portfolio_physical += invest_physical

        liabilities = 0.0
        for loan in active_loans:
            insts = loan_installments[loan.id]
            due_this_month = [i for i in insts if cur_date < i.due_date <= next_date]
            for i in due_this_month:
                month_delta -= convert_amount(float(i.total_amount), loan_currency[loan.id], target_currency, FxRates) or 0
            past_or_now = [i for i in insts if i.due_date <= next_date]
            remaining = float(past_or_now[-1].remaining_principal_after) if past_or_now else float(loan.principal)
            liabilities += convert_amount(remaining, loan_currency[loan.id], target_currency, FxRates) or 0

        bank_cash += month_delta
        if has_goals:
            bank_cash_goals += month_delta
            # target_amount est saisi dans la devise par défaut (target_currency), même convention
            # que Budgets.amount_allocated — pas de conversion à appliquer ici.
            for g in goals:
                occs_in_month = [o for o in goal_occurrences[g['id']] if cur_date < o <= next_date]
                if not occs_in_month:
                    continue
                bank_cash_goals -= float(g['target_amount']) * len(occs_in_month)
                goal_balances[g['id']].append(bank_cash_goals)

        portfolio_value = portfolio_financial + portfolio_physical
        financial_net_worth = portfolio_value - liabilities
        points.append({
            'date': next_date.isoformat(),
            'bank_cash': round(bank_cash, 2),
            'bank_cash_with_goals': round(bank_cash_goals, 2) if has_goals else None,
            'portfolio_value': round(portfolio_value, 2),
            'liabilities': round(liabilities, 2),
            'financial_net_worth': round(financial_net_worth, 2),
        })
        cur_date = next_date

    # Un objectif est "feasible" si la trésorerie-avec-objectifs n'est jamais tombée sous zéro aux
    # mois où IL retire de l'argent (attribution approximative en cas d'objectifs concurrents
    # partageant le même pool — le pire solde atteint reste correct, mais désigner LEQUEL des
    # objectifs simultanés "cause" le déficit n'a pas de réponse unique). 'out_of_range' = aucune
    # occurrence dans l'horizon simulé (déjà passé, ou commence après l'horizon demandé).
    goals_result = []
    for g in goals:
        balances = goal_balances[g['id']]
        if not balances:
            goals_result.append({
                'id': g['id'], 'name': g['name'], 'status': 'out_of_range',
                'balance_after': None, 'min_balance_during': None,
            })
            continue
        min_balance = min(balances)
        goals_result.append({
            'id': g['id'], 'name': g['name'],
            'status': 'feasible' if min_balance >= 0 else 'at_risk',
            'balance_after': round(balances[-1], 2),
            'min_balance_during': round(min_balance, 2),
        })

    return {
        'currency': target_currency,
        'params': {
            'horizon_months': horizon_months,
            'growth_financial_pct': growth_financial_pct,
            'growth_physical_pct': growth_physical_pct,
            'growth_cash_pct': growth_cash_pct,
            'avg_monthly_net_flow': round(avg_monthly_net_flow, 2),
            'avg_monthly_net_flow_auto': net_flow_auto,
            'invest_mode': invest_mode,
            'invest_financial_amount': round(invest_financial, 2),
            'invest_physical_amount': round(invest_physical, 2),
        },
        'points': points,
        'goals_result': goals_result,
    }
