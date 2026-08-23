from datetime import date, datetime

from marshmallow import Schema, fields, ValidationError, validate
from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.config import HttpCode, VAR_API_ROOT_PATH as ROOT_PATH, VAR_PERMISSIONS_LIST
from backend.utils.api_responses import json_response
from backend.utils.restricted_by_permission import restricted_by_permission
from backend.utils.recurrence import next_occurrence
from backend.utils.amortization import build_schedule, regenerate_from_revision

LOANS_PERM = VAR_PERMISSIONS_LIST['Crédits']['id']


class AddLoanSchema(Schema):
    name = fields.String(required=True)
    principal = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0.01))
    annual_rate = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0))
    term_months = fields.Integer(required=True, validate=validate.Range(min=1))
    start_date = fields.Date(required=True)
    payment_day = fields.Integer(required=True, validate=validate.Range(min=1, max=31))
    payment_account_id = fields.UUID(required=True)
    interest_expense_account_id = fields.UUID(required=True)
    insurance_expense_account_id = fields.UUID(load_default=None, allow_none=True)
    insurance_monthly_amount = fields.Decimal(load_default=None, allow_none=True, as_string=False)
    category_id = fields.UUID(load_default=None, allow_none=True)
    auto_debit = fields.Boolean(load_default=False)
    is_existing_loan = fields.Boolean(load_default=False)


class UpdateLoanSchema(Schema):
    loan_id = fields.UUID(required=True)
    name = fields.String(required=True)
    payment_account_id = fields.UUID(required=True)
    interest_expense_account_id = fields.UUID(required=True)
    insurance_expense_account_id = fields.UUID(load_default=None, allow_none=True)
    insurance_monthly_amount = fields.Decimal(load_default=None, allow_none=True, as_string=False)
    category_id = fields.UUID(load_default=None, allow_none=True)
    auto_debit = fields.Boolean(load_default=False)


class GetLoanSchema(Schema):
    loan_id = fields.UUID()


class LoanIdSchema(Schema):
    loan_id = fields.UUID(required=True)


class DeleteLoanSchema(Schema):
    loan_id = fields.UUID(required=True)


class ExecuteInstallmentSchema(Schema):
    installment_id = fields.UUID(required=True)


class AddRateRevisionSchema(Schema):
    loan_id = fields.UUID(required=True)
    effective_date = fields.Date(required=True)
    new_annual_rate = fields.Decimal(required=True, as_string=False, validate=validate.Range(min=0))
    recalc_mode = fields.String(required=True, validate=validate.OneOf(('keep_term', 'keep_payment')))


class PayoffLoanSchema(Schema):
    loan_id = fields.UUID(required=True)


def _get_owned_account(Accounts, user_id, account_id, expected_type=None):
    account = Accounts.query.filter(Accounts.id == account_id, Accounts.user_id == user_id).first()
    if not account:
        return None, "compte introuvable"
    if expected_type and account.account_type != expected_type:
        return None, f"doit être un compte de type {expected_type}"
    return account, None


def _live_remaining_principal(liability_account):
    if not liability_account:
        return 0.0
    return round(float(liability_account.total_spent or 0) - float(liability_account.total_earned or 0), 2)


def _loan_to_dict(loan, Accounts, LoanInstallments, Commodities):
    installments = (LoanInstallments.query.filter_by(loan_id=loan.id)
                     .order_by(LoanInstallments.installment_number).all())
    unpaid = [i for i in installments if not i.is_paid]
    next_installment = unpaid[0] if unpaid else None
    today = date.today()

    liability_account = Accounts.query.filter_by(id=loan.liability_account_id).first()
    # Devise du prêt = celle de son compte Liability (verrouillée sur celle du compte de
    # prélèvement à la création, voir add_loan/update_loan) — exposée explicitement pour que le
    # frontend n'affiche jamais un montant sans indiquer sa devise (un crédit peut être dans une
    # devise différente de la devise d'affichage par défaut de l'utilisateur).
    currency = None
    if liability_account:
        commodity = Commodities.query.filter_by(id=liability_account.currency_id).first()
        currency = commodity.short_name if commodity else None

    return {
        'id': str(loan.id),
        'user_id': str(loan.user_id),
        'name': loan.name,
        'currency': currency,
        'principal': float(loan.principal),
        'annual_rate': float(loan.annual_rate),
        'term_months': loan.term_months,
        'start_date': loan.start_date.isoformat() if loan.start_date else None,
        'payment_day': loan.payment_day,
        'payment_account_id': str(loan.payment_account_id),
        'interest_expense_account_id': str(loan.interest_expense_account_id),
        'insurance_expense_account_id': str(loan.insurance_expense_account_id) if loan.insurance_expense_account_id else None,
        'insurance_monthly_amount': float(loan.insurance_monthly_amount) if loan.insurance_monthly_amount is not None else None,
        'liability_account_id': str(loan.liability_account_id),
        'equity_opening_account_id': str(loan.equity_opening_account_id) if loan.equity_opening_account_id else None,
        'category_id': str(loan.category_id) if loan.category_id else None,
        'auto_debit': loan.auto_debit,
        'is_existing_loan': loan.is_existing_loan,
        'is_closed': loan.is_closed,
        'closed_at': loan.closed_at.isoformat() if loan.closed_at else None,
        'remaining_principal': _live_remaining_principal(liability_account),
        # Coût total des intérêts sur toute la durée du prêt selon l'échéancier ACTUEL (échéances
        # payées + à venir) — évolue si une révision de taux régénère l'échéancier restant.
        'total_interest_cost': round(sum(float(i.interest_portion) for i in installments), 2),
        'installment_count': len(installments),
        'paid_count': len(installments) - len(unpaid),
        'next_installment': {
            'id': str(next_installment.id),
            'installment_number': next_installment.installment_number,
            'due_date': next_installment.due_date.isoformat(),
            'total_amount': float(next_installment.total_amount),
            'is_overdue': next_installment.due_date < today,
        } if next_installment else None,
        'created_at': loan.created_at.isoformat() if loan.created_at else None,
        'updated_at': loan.updated_at.isoformat() if loan.updated_at else None,
    }


def _installment_to_dict(inst):
    return {
        'id': str(inst.id),
        'loan_id': str(inst.loan_id),
        'installment_number': inst.installment_number,
        'due_date': inst.due_date.isoformat(),
        'principal_portion': float(inst.principal_portion),
        'interest_portion': float(inst.interest_portion),
        'insurance_portion': float(inst.insurance_portion),
        'total_amount': float(inst.total_amount),
        'remaining_principal_after': float(inst.remaining_principal_after),
        'is_paid': inst.is_paid,
        'paid_at': inst.paid_at.isoformat() if inst.paid_at else None,
        'transaction_id': str(inst.transaction_id) if inst.transaction_id else None,
        'is_overdue': (not inst.is_paid) and inst.due_date < date.today(),
    }


def _revision_to_dict(rev):
    return {
        'id': str(rev.id),
        'loan_id': str(rev.loan_id),
        'effective_date': rev.effective_date.isoformat(),
        'new_annual_rate': float(rev.new_annual_rate),
        'recalc_mode': rev.recalc_mode,
        'created_at': rev.created_at.isoformat() if rev.created_at else None,
    }


class LoansRoutes:
    def __init__(self, app, DB, Loans, LoanInstallments, LoanRateRevisions, Users,
                 Transactions, Splits, Accounts, Commodities):
        ROUTE_PATH = f"{ROOT_PATH}/loans"

        @app.route(f"{ROUTE_PATH}", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def get_loans():
            try:
                data = GetLoanSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            if data.get('loan_id'):
                loan = Loans.query.filter(Loans.id == data['loan_id'], Loans.user_id == user_id).first()
                if not loan:
                    return json_response('Prêt introuvable', HttpCode.NOT_FOUND)
                return json_response(_loan_to_dict(loan, Accounts, LoanInstallments, Commodities), HttpCode.OK)

            loans = Loans.query.filter(Loans.user_id == user_id).order_by(Loans.name).all()
            return json_response([_loan_to_dict(l, Accounts, LoanInstallments, Commodities) for l in loans], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def add_loan():
            try:
                data = AddLoanSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            if Loans.query.filter(Loans.user_id == user_id, Loans.name == data['name']).first():
                return json_response('Un prêt avec ce nom existe déjà', HttpCode.CONFLICT)

            payment_account, err = _get_owned_account(Accounts, user_id, data['payment_account_id'], 'Current')
            if err:
                return json_response(f"Compte de prélèvement : {err}", HttpCode.BAD_REQUEST)

            interest_account, err = _get_owned_account(
                Accounts, user_id, data['interest_expense_account_id'], 'Expense')
            if err:
                return json_response(f"Compte d'intérêts : {err}", HttpCode.BAD_REQUEST)

            insurance_account = None
            if data.get('insurance_expense_account_id'):
                insurance_account, err = _get_owned_account(
                    Accounts, user_id, data['insurance_expense_account_id'], 'Expense')
                if err:
                    return json_response(f"Compte d'assurance : {err}", HttpCode.BAD_REQUEST)

            is_existing = data.get('is_existing_loan', False)

            for label, acc in (("intérêts", interest_account), ("assurance", insurance_account)):
                if acc and str(acc.currency_id) != str(payment_account.currency_id):
                    return json_response(
                        f"Le compte de {label} doit avoir la même devise que le compte de prélèvement",
                        HttpCode.BAD_REQUEST)

            try:
                liability_account = Accounts(
                    user_id=user_id,
                    name=f"Prêt — {data['name']}",
                    account_type='Liability',
                    currency_id=payment_account.currency_id,
                    is_virtual=False,
                    description=f"Compte de passif généré automatiquement pour le prêt « {data['name']} »",
                )
                DB.session.add(liability_account)
                DB.session.flush()

                # Contrepartie d'ouverture pour un crédit déjà en cours : auto-générée (comme le
                # compte Liability ci-dessus), plus besoin que l'utilisateur en choisisse un
                # existant — subtype 'loan' pour la distinguer d'un vrai compte Equity (PEA...) et
                # l'exclure de la liste des comptes (voir Accounts.vue).
                equity_account = None
                if is_existing:
                    equity_account = Accounts(
                        user_id=user_id,
                        name=f"Ouverture — {data['name']}",
                        account_type='Equity',
                        account_subtype='loan',
                        currency_id=payment_account.currency_id,
                        is_virtual=False,
                        description=(f"Contrepartie comptable générée automatiquement pour "
                                     f"l'ouverture du prêt « {data['name']} » (crédit déjà en cours)"),
                    )
                    DB.session.add(equity_account)
                    DB.session.flush()

                loan = Loans(
                    user_id=user_id,
                    name=data['name'],
                    principal=data['principal'],
                    annual_rate=data['annual_rate'],
                    term_months=data['term_months'],
                    start_date=data['start_date'],
                    payment_day=data['payment_day'],
                    payment_account_id=payment_account.id,
                    interest_expense_account_id=interest_account.id,
                    insurance_expense_account_id=insurance_account.id if insurance_account else None,
                    insurance_monthly_amount=data.get('insurance_monthly_amount'),
                    liability_account_id=liability_account.id,
                    equity_opening_account_id=equity_account.id if equity_account else None,
                    category_id=data.get('category_id'),
                    auto_debit=data.get('auto_debit', False),
                    is_existing_loan=is_existing,
                )
                DB.session.add(loan)
                DB.session.flush()

                principal = float(data['principal'])
                opening_dt = datetime.combine(data['start_date'], datetime.min.time())
                tx = Transactions(
                    user_id=user_id,
                    currency_id=payment_account.currency_id,
                    post_date=opening_dt,
                    effective_date=opening_dt,
                    description=(f"Situation d'ouverture du prêt « {data['name']} »" if is_existing
                                  else f"Déblocage du prêt « {data['name']} »"),
                    is_cleared=True,
                )
                DB.session.add(tx)
                DB.session.flush()
                # Le compte Liability est débité de -principal quel que soit le mode : sa balance
                # (total_earned - total_spent) reste ainsi en permanence égale à -(capital restant
                # dû), voir la note sur la convention de signe dans loans.py.
                DB.session.add(Splits(tx_id=tx.id, account_id=liability_account.id, quantity=-principal))
                if is_existing:
                    DB.session.add(Splits(tx_id=tx.id, account_id=equity_account.id, quantity=principal))
                else:
                    DB.session.add(Splits(tx_id=tx.id, account_id=payment_account.id, quantity=principal))
                loan.opening_transaction_id = tx.id

                first_due = next_occurrence('monthly', data['payment_day'], None, None, after=data['start_date'])
                schedule = build_schedule(
                    principal, float(data['annual_rate']), data['term_months'], first_due, data['payment_day'],
                    float(data.get('insurance_monthly_amount') or 0),
                )
                for row in schedule:
                    DB.session.add(LoanInstallments(loan_id=loan.id, **row))

                DB.session.commit()
                return json_response(_loan_to_dict(loan, Accounts, LoanInstallments, Commodities), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['PATCH'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def update_loan():
            try:
                data = UpdateLoanSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            loan = Loans.query.filter(Loans.id == data['loan_id'], Loans.user_id == user_id).first()
            if not loan:
                return json_response('Prêt introuvable', HttpCode.NOT_FOUND)
            if loan.is_closed:
                return json_response('Ce prêt est clôturé', HttpCode.BAD_REQUEST)

            if data['name'] != loan.name and Loans.query.filter(
                    Loans.user_id == user_id, Loans.name == data['name']).first():
                return json_response('Un prêt avec ce nom existe déjà', HttpCode.CONFLICT)

            payment_account, err = _get_owned_account(Accounts, user_id, data['payment_account_id'], 'Current')
            if err:
                return json_response(f"Compte de prélèvement : {err}", HttpCode.BAD_REQUEST)
            interest_account, err = _get_owned_account(
                Accounts, user_id, data['interest_expense_account_id'], 'Expense')
            if err:
                return json_response(f"Compte d'intérêts : {err}", HttpCode.BAD_REQUEST)

            insurance_account = None
            if data.get('insurance_expense_account_id'):
                insurance_account, err = _get_owned_account(
                    Accounts, user_id, data['insurance_expense_account_id'], 'Expense')
                if err:
                    return json_response(f"Compte d'assurance : {err}", HttpCode.BAD_REQUEST)

            # Le compte Liability du prêt est créé une fois pour toutes à la devise du compte de
            # prélèvement d'origine et ne change plus jamais — si l'utilisateur changeait ensuite
            # payment_account_id vers un compte d'une autre devise, les futures échéances
            # posteraient les montants (calculés dans la devise d'origine) tels quels dans la
            # nouvelle devise, sans conversion : un montant de 1693.87 EUR deviendrait 1693.87 USD.
            # On verrouille donc la devise du compte de prélèvement sur celle du compte Liability,
            # comme le fait déjà l'appli pour les comptes parent/enfant.
            liability_account = Accounts.query.filter_by(id=loan.liability_account_id).first()
            if liability_account and str(payment_account.currency_id) != str(liability_account.currency_id):
                return json_response(
                    "Le compte de prélèvement doit rester dans la devise d'origine du crédit",
                    HttpCode.BAD_REQUEST)

            for label, acc in (("intérêts", interest_account), ("assurance", insurance_account)):
                if acc and str(acc.currency_id) != str(payment_account.currency_id):
                    return json_response(
                        f"Le compte de {label} doit avoir la même devise que le compte de prélèvement",
                        HttpCode.BAD_REQUEST)

            try:
                loan.name = data['name']
                loan.auto_debit = data.get('auto_debit', loan.auto_debit)
                loan.payment_account_id = payment_account.id
                loan.interest_expense_account_id = interest_account.id
                loan.category_id = data.get('category_id')

                new_insurance_account_id = insurance_account.id if insurance_account else None
                new_insurance_amount = data.get('insurance_monthly_amount')
                old_insurance_amount = float(loan.insurance_monthly_amount) if loan.insurance_monthly_amount is not None else None
                insurance_changed = (
                    new_insurance_account_id != loan.insurance_expense_account_id or
                    (float(new_insurance_amount) if new_insurance_amount is not None else None) != old_insurance_amount
                )
                loan.insurance_expense_account_id = new_insurance_account_id
                loan.insurance_monthly_amount = new_insurance_amount

                if insurance_changed:
                    unpaid = LoanInstallments.query.filter(
                        LoanInstallments.loan_id == loan.id, LoanInstallments.is_paid == False).all()
                    for inst in unpaid:
                        inst.insurance_portion = round(float(new_insurance_amount or 0), 2)
                        inst.total_amount = round(
                            float(inst.principal_portion) + float(inst.interest_portion) + float(inst.insurance_portion), 2)

                DB.session.commit()
                return json_response(_loan_to_dict(loan, Accounts, LoanInstallments, Commodities), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}", methods=['DELETE'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def delete_loan():
            try:
                data = DeleteLoanSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            loan = Loans.query.filter(Loans.id == data['loan_id'], Loans.user_id == user_id).first()
            if not loan:
                return json_response('Prêt introuvable', HttpCode.NOT_FOUND)

            if LoanInstallments.query.filter(
                    LoanInstallments.loan_id == loan.id, LoanInstallments.is_paid == True).first():
                return json_response(
                    "Impossible de supprimer un prêt avec des échéances déjà exécutées — "
                    "utilisez le remboursement anticipé total",
                    HttpCode.CONFLICT)

            # Un prêt clôturé par remboursement anticipé total (payoff_loan) n'a plus d'échéance
            # is_paid=True — payoff_loan les supprime au lieu de les marquer payées — donc le garde-
            # fou ci-dessus ne suffit pas à le détecter. Sans ce contrôle, la suppression du compte
            # de passif plus bas fait disparaître (ON DELETE CASCADE) le split de remboursement sans
            # toucher à la transaction elle-même, qui reste orpheline avec un seul split déséquilibré.
            if loan.is_closed:
                return json_response(
                    "Impossible de supprimer un prêt déjà remboursé (remboursement anticipé total) — "
                    "sa transaction de remboursement doit être conservée",
                    HttpCode.CONFLICT)

            try:
                liability_account_id = loan.liability_account_id
                equity_account_id = loan.equity_opening_account_id
                opening_tx_id = loan.opening_transaction_id
                DB.session.delete(loan)
                DB.session.flush()
                if opening_tx_id:
                    tx = Transactions.query.filter_by(id=opening_tx_id).first()
                    if tx:
                        DB.session.delete(tx)
                        DB.session.flush()
                for account_id, label in ((liability_account_id, "de passif"), (equity_account_id, "d'ouverture")):
                    if not account_id:
                        continue
                    account = Accounts.query.filter_by(id=account_id).first()
                    if not account:
                        continue
                    # Compte Equity de contrepartie éventuellement choisi par l'utilisateur parmi
                    # ses comptes existants (anciens prêts créés avant l'auto-génération, subtype
                    # 'loan') — un vrai compte à lui ne doit jamais être supprimé automatiquement.
                    if account.account_type == 'Equity' and account.account_subtype != 'loan':
                        continue
                    # Filet de sécurité : si un split existe encore sur ce compte au-delà de la
                    # transaction d'ouverture déjà supprimée ci-dessus (ex. écriture manuelle
                    # ajoutée par l'utilisateur en mode avancé), ne pas le supprimer — la cascade
                    # orphelinerait la transaction qui le porte (même bug que celui corrigé sur
                    # delete_account()).
                    if Splits.query.filter(Splits.account_id == account.id).first():
                        DB.session.rollback()
                        return json_response(
                            f"Impossible de supprimer ce prêt : son compte {label} a encore des "
                            "transactions liées",
                            HttpCode.CONFLICT)
                    DB.session.delete(account)
                DB.session.commit()
                return json_response('Prêt supprimé', HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/installments", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def get_loan_installments():
            try:
                data = LoanIdSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            loan = Loans.query.filter(Loans.id == data['loan_id'], Loans.user_id == user_id).first()
            if not loan:
                return json_response('Prêt introuvable', HttpCode.NOT_FOUND)

            installments = (LoanInstallments.query.filter_by(loan_id=loan.id)
                             .order_by(LoanInstallments.installment_number).all())
            return json_response([_installment_to_dict(i) for i in installments], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/execute", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def execute_loan_installment_route():
            try:
                data = ExecuteInstallmentSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            installment = LoanInstallments.query.filter_by(id=data['installment_id']).first()
            if not installment:
                return json_response('Échéance introuvable', HttpCode.NOT_FOUND)
            loan = Loans.query.filter(Loans.id == installment.loan_id, Loans.user_id == user_id).first()
            if not loan:
                return json_response('Prêt introuvable', HttpCode.NOT_FOUND)
            if loan.is_closed:
                return json_response('Ce prêt est clôturé', HttpCode.BAD_REQUEST)
            if installment.is_paid:
                return json_response('Cette échéance est déjà payée', HttpCode.BAD_REQUEST)

            try:
                from backend.scheduler import execute_one_loan_installment
                execute_one_loan_installment(installment, loan, DB, Transactions, Splits, Accounts)
                return json_response(_loan_to_dict(loan, Accounts, LoanInstallments, Commodities), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/rate-revisions", methods=['GET'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def get_loan_rate_revisions():
            try:
                data = LoanIdSchema().load(request.args)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            loan = Loans.query.filter(Loans.id == data['loan_id'], Loans.user_id == user_id).first()
            if not loan:
                return json_response('Prêt introuvable', HttpCode.NOT_FOUND)

            revisions = (LoanRateRevisions.query.filter_by(loan_id=loan.id)
                         .order_by(LoanRateRevisions.effective_date).all())
            return json_response([_revision_to_dict(r) for r in revisions], HttpCode.OK)

        @app.route(f"{ROUTE_PATH}/rate-revisions", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def add_loan_rate_revision():
            try:
                data = AddRateRevisionSchema().load(request.json)
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            loan = Loans.query.filter(Loans.id == data['loan_id'], Loans.user_id == user_id).first()
            if not loan:
                return json_response('Prêt introuvable', HttpCode.NOT_FOUND)
            if loan.is_closed:
                return json_response('Ce prêt est clôturé', HttpCode.BAD_REQUEST)

            swept = (LoanInstallments.query
                     .filter(LoanInstallments.loan_id == loan.id, LoanInstallments.is_paid == False,
                             LoanInstallments.due_date >= data['effective_date'])
                     .order_by(LoanInstallments.installment_number).all())
            if not swept:
                return json_response(
                    "Aucune échéance future à recalculer à partir de cette date", HttpCode.BAD_REQUEST)

            current_count = len(swept)
            current_total_payment = float(swept[0].principal_portion) + float(swept[0].interest_portion)
            first_installment_number = swept[0].installment_number

            # Ancrer sur l'échéance PRÉCÉDENTE de l'échéancier existant (peu importe si elle est déjà
            # payée) plutôt que sur la dernière effectivement payée à l'instant T : si effective_date
            # est loin dans le futur, des échéances entre aujourd'hui et cette date existent déjà,
            # non payées mais déjà correctement chaînées (remaining_principal_after cohérent) — s'en
            # tenir à "dernière payée à la création de la révision" ignorait leur remboursement à
            # venir et gonflait artificiellement le capital restant repris par le nouvel échéancier
            # (bug constaté : capital restant qui REMONTE juste après la révision au lieu de baisser).
            prior_installment = (LoanInstallments.query
                                  .filter(LoanInstallments.loan_id == loan.id,
                                          LoanInstallments.installment_number == first_installment_number - 1)
                                  .first())
            base_remaining_principal = (float(prior_installment.remaining_principal_after)
                                         if prior_installment else float(loan.principal))

            try:
                new_rows = regenerate_from_revision(
                    base_remaining_principal, float(data['new_annual_rate']), data['recalc_mode'],
                    swept[0].due_date, loan.payment_day, current_count, current_total_payment,
                    first_installment_number, float(loan.insurance_monthly_amount or 0),
                )
            except ValueError as err:
                return json_response(str(err), HttpCode.BAD_REQUEST)

            try:
                revision = LoanRateRevisions(
                    loan_id=loan.id, effective_date=data['effective_date'],
                    new_annual_rate=data['new_annual_rate'], recalc_mode=data['recalc_mode'],
                )
                DB.session.add(revision)
                DB.session.flush()

                for inst in swept:
                    DB.session.delete(inst)
                DB.session.flush()

                for row in new_rows:
                    DB.session.add(LoanInstallments(loan_id=loan.id, rate_revision_id=revision.id, **row))

                loan.annual_rate = data['new_annual_rate']
                loan.term_months = first_installment_number - 1 + len(new_rows)
                DB.session.commit()
                return json_response(_loan_to_dict(loan, Accounts, LoanInstallments, Commodities), HttpCode.CREATED)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)

        @app.route(f"{ROUTE_PATH}/payoff", methods=['POST'])
        @jwt_required()
        @restricted_by_permission(Users, LOANS_PERM)
        def payoff_loan():
            try:
                data = PayoffLoanSchema().load(request.json or {})
            except ValidationError as err:
                return json_response(err.messages, HttpCode.BAD_REQUEST)

            user_id = get_jwt_identity()
            loan = Loans.query.filter(Loans.id == data['loan_id'], Loans.user_id == user_id).first()
            if not loan:
                return json_response('Prêt introuvable', HttpCode.NOT_FOUND)
            if loan.is_closed:
                return json_response('Ce prêt est déjà clôturé', HttpCode.BAD_REQUEST)

            liability_account = Accounts.query.filter_by(id=loan.liability_account_id).first()
            remaining = _live_remaining_principal(liability_account)
            if remaining <= 0:
                return json_response('Ce prêt est déjà soldé', HttpCode.BAD_REQUEST)

            try:
                payment_account = Accounts.query.filter_by(id=loan.payment_account_id).first()
                payoff_dt = datetime.combine(date.today(), datetime.min.time())
                tx = Transactions(
                    user_id=user_id, currency_id=payment_account.currency_id,
                    post_date=payoff_dt, effective_date=payoff_dt,
                    description=f"Remboursement anticipé total — {loan.name}", is_cleared=True,
                )
                DB.session.add(tx)
                DB.session.flush()
                DB.session.add(Splits(tx_id=tx.id, account_id=payment_account.id, quantity=-remaining))
                DB.session.add(Splits(tx_id=tx.id, account_id=loan.liability_account_id, quantity=remaining))

                LoanInstallments.query.filter(
                    LoanInstallments.loan_id == loan.id, LoanInstallments.is_paid == False
                ).delete()

                loan.is_closed = True
                loan.closed_at = payoff_dt
                DB.session.commit()
                return json_response(_loan_to_dict(loan, Accounts, LoanInstallments, Commodities), HttpCode.OK)
            except Exception as error:
                DB.session.rollback()
                return json_response(str(error), HttpCode.SERVER_ERROR)
