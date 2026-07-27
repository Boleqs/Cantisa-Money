"""initial schema (squash of 16 migrations, v1 sur l'état actuel)

Revision ID: 15d48a123464
Revises: 
Create Date: 2026-07-27 23:00:00.000000

App pas encore en prod : fusion de toutes les migrations précédentes (0bee1c5b7470 →
c1f6a9b3e7d5) en une seule, générée par pg_dump --schema-only sur la base locale à jour
plutôt que par autogenerate sur les modèles SQLAlchemy (qui ont un léger décalage connu,
ex. le CheckConstraint account_type pas mis à jour après l’ajout de Liability, et qui ne
capturent de toute façon pas les triggers/fonctions Postgres personnalisés ci-dessous).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '15d48a123464'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(SCHEMA_SQL)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")


SCHEMA_SQL = """CREATE FUNCTION public.check_category_id() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        IF NEW.category_id IS NULL THEN
            RETURN NEW;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM categories WHERE id = NEW.category_id AND user_id = NEW.user_id) THEN
            RAISE EXCEPTION 'Invalid category_id % for user_id %', NEW.category_id, NEW.user_id;
        END IF;
        RETURN NEW;
    END;
    $$;

CREATE FUNCTION public.handle_account_parent_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            PERFORM propagate_consolidated_totals(OLD.parent_id);
            RETURN OLD;
        END IF;

        IF TG_OP = 'UPDATE' AND OLD.parent_id IS DISTINCT FROM NEW.parent_id THEN
            PERFORM propagate_consolidated_totals(OLD.parent_id);
        END IF;

        UPDATE accounts SET
            consolidated_earned = total_earned + COALESCE((
                SELECT SUM(consolidated_earned) FROM accounts WHERE parent_id = NEW.id
            ), 0),
            consolidated_spent = total_spent + COALESCE((
                SELECT SUM(consolidated_spent) FROM accounts WHERE parent_id = NEW.id
            ), 0)
        WHERE id = NEW.id;

        PERFORM propagate_consolidated_totals(NEW.parent_id);
        RETURN NEW;
    END;
    $$;

CREATE FUNCTION public.propagate_consolidated_totals(start_id uuid) RETURNS void
    LANGUAGE plpgsql
    AS $$
    DECLARE
        current_id UUID := start_id;
        current_parent UUID;
        own_e NUMERIC;
        own_s NUMERIC;
        children_e NUMERIC;
        children_s NUMERIC;
        depth INT := 0;
    BEGIN
        WHILE current_id IS NOT NULL AND depth < 100 LOOP
            SELECT total_earned, total_spent, parent_id INTO own_e, own_s, current_parent
            FROM accounts WHERE id = current_id;

            IF NOT FOUND THEN
                EXIT;
            END IF;

            SELECT COALESCE(SUM(consolidated_earned), 0), COALESCE(SUM(consolidated_spent), 0)
            INTO children_e, children_s
            FROM accounts WHERE parent_id = current_id;

            UPDATE accounts
            SET consolidated_earned = own_e + children_e,
                consolidated_spent = own_s + children_s
            WHERE id = current_id;

            current_id := current_parent;
            depth := depth + 1;
        END LOOP;
    END;
    $$;

CREATE FUNCTION public.update_account_totals() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        affected_account_id UUID;
    BEGIN
        IF TG_OP = 'UPDATE' AND OLD.account_id IS DISTINCT FROM NEW.account_id THEN
            UPDATE accounts SET
                total_earned = COALESCE((
                    SELECT SUM(quantity) FROM splits
                    WHERE account_id = OLD.account_id AND quantity > 0
                ), 0),
                total_spent = COALESCE((
                    SELECT SUM(-quantity) FROM splits
                    WHERE account_id = OLD.account_id AND quantity < 0
                ), 0)
            WHERE id = OLD.account_id;
            PERFORM propagate_consolidated_totals(OLD.account_id);
        END IF;

        IF TG_OP = 'DELETE' THEN
            affected_account_id := OLD.account_id;
        ELSE
            affected_account_id := NEW.account_id;
        END IF;

        UPDATE accounts SET
            total_earned = COALESCE((
                SELECT SUM(quantity) FROM splits
                WHERE account_id = affected_account_id AND quantity > 0
            ), 0),
            total_spent = COALESCE((
                SELECT SUM(-quantity) FROM splits
                WHERE account_id = affected_account_id AND quantity < 0
            ), 0)
        WHERE id = affected_account_id;

        PERFORM propagate_consolidated_totals(affected_account_id);

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END;
    $$;

CREATE FUNCTION public.update_budget_spent() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE
        affected_budget RECORD;
        target_currency VARCHAR;
        new_amount_spent NUMERIC;
        new_incomplete BOOLEAN;
        split_ref RECORD;
    BEGIN
        IF TG_OP = 'DELETE' THEN
            split_ref := OLD;
        ELSE
            split_ref := NEW;
        END IF;

        FOR affected_budget IN
            SELECT DISTINCT b.id, b.start_date, b.end_date, b.user_id
            FROM budgets b
            WHERE
                EXISTS (
                    SELECT 1 FROM budget_accounts ba
                    WHERE ba.budget_id = b.id AND ba.account_id = split_ref.account_id
                )
                OR EXISTS (
                    SELECT 1 FROM budget_categories bc
                    JOIN transactions t ON t.id = split_ref.tx_id
                    WHERE bc.budget_id = b.id
                      AND bc.category_id = t.category_id
                      AND t.category_id IS NOT NULL
                )
                OR EXISTS (
                    SELECT 1 FROM budget_tags bt
                    JOIN tags_on_split tos ON tos.tag_id = bt.tag_id
                    WHERE bt.budget_id = b.id AND tos.split_id = split_ref.id
                )
        LOOP
            SELECT COALESCE(us.currency, 'EUR') INTO target_currency
            FROM user_settings us WHERE us.user_id = affected_budget.user_id;
            IF target_currency IS NULL THEN
                target_currency := 'EUR';
            END IF;

            SELECT
                COALESCE(SUM(CASE
                    WHEN c.short_name = target_currency THEN -s.quantity
                    WHEN fx.rate IS NOT NULL THEN -s.quantity * fx.rate
                    ELSE NULL
                END), 0),
                COALESCE(bool_or(c.short_name <> target_currency AND fx.rate IS NULL), false)
            INTO new_amount_spent, new_incomplete
            FROM splits s
            JOIN transactions t ON t.id = s.tx_id
            JOIN accounts a ON a.id = s.account_id
            JOIN commodities c ON c.id = a.currency_id
            LEFT JOIN LATERAL (
                SELECT fr.rate FROM fx_rates fr
                WHERE fr.from_code = c.short_name AND fr.to_code = target_currency
                ORDER BY fr.rate_date DESC LIMIT 1
            ) fx ON c.short_name <> target_currency
            WHERE
                t.post_date BETWEEN affected_budget.start_date AND affected_budget.end_date
                AND (
                    EXISTS (
                        SELECT 1 FROM budget_accounts ba
                        WHERE ba.budget_id = affected_budget.id AND ba.account_id = s.account_id
                    )
                    OR (
                        a.account_type NOT IN ('Expense', 'Income')
                        AND t.category_id IS NOT NULL
                        AND EXISTS (
                            SELECT 1 FROM budget_categories bc
                            WHERE bc.budget_id = affected_budget.id AND bc.category_id = t.category_id
                        )
                    )
                    OR (
                        a.account_type NOT IN ('Expense', 'Income')
                        AND EXISTS (
                            SELECT 1 FROM tags_on_split tos
                            JOIN budget_tags bt ON bt.tag_id = tos.tag_id
                            WHERE tos.split_id = s.id AND bt.budget_id = affected_budget.id
                        )
                    )
                );

            UPDATE budgets SET amount_spent = new_amount_spent, amount_spent_incomplete = new_incomplete
            WHERE id = affected_budget.id;
        END LOOP;

        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END;
    $$;

CREATE FUNCTION public.update_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$;

CREATE TABLE public.accounts (
    user_id uuid,
    id uuid NOT NULL,
    name character varying(128) NOT NULL,
    parent_id uuid,
    account_type character varying(64) NOT NULL,
    account_subtype character varying(64),
    currency_id uuid NOT NULL,
    description character varying(1024),
    total_spent numeric NOT NULL,
    total_earned numeric NOT NULL,
    is_virtual boolean NOT NULL,
    is_hidden boolean NOT NULL,
    code character varying(64),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    consolidated_earned numeric NOT NULL,
    consolidated_spent numeric NOT NULL,
    tax_treatment character varying(32),
    is_closed boolean NOT NULL,
    closed_at timestamp without time zone,
    CONSTRAINT accounts_account_type_check CHECK (((account_type)::text = ANY ((ARRAY['Income'::character varying, 'Expense'::character varying, 'Equity'::character varying, 'Assets'::character varying, 'Current'::character varying, 'Liability'::character varying])::text[]))),
    CONSTRAINT accounts_check CHECK (((((account_type)::text = 'Equity'::text) AND ((account_subtype)::text = ANY ((ARRAY['fr_PEA'::character varying, 'Other'::character varying])::text[]))) OR (account_subtype IS NULL))),
    CONSTRAINT ck_accounts_tax_treatment CHECK ((((tax_treatment)::text = ANY ((ARRAY['taxable_income'::character varying, 'deductible'::character varying, 'real_estate_income'::character varying, 'real_estate_expense'::character varying])::text[])) OR (tax_treatment IS NULL)))
);

CREATE TABLE public.asset_disposal (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    possession_id uuid NOT NULL,
    quantity integer NOT NULL,
    sale_price numeric,
    sale_price_native numeric,
    sale_date timestamp without time zone NOT NULL,
    dest_account_id uuid,
    tx_id uuid,
    source_split_id uuid,
    dest_split_id uuid,
    realized_gain numeric,
    holding_period_days integer,
    created_at timestamp without time zone,
    CONSTRAINT ck_asset_disposal_quantity CHECK (((quantity <= 1000000000) AND (quantity >= 0)))
);

CREATE TABLE public.asset_possession (
    user_id uuid,
    id uuid NOT NULL,
    asset_id uuid,
    account_id uuid,
    source_account_id uuid,
    tx_id uuid,
    source_split_id uuid,
    dest_split_id uuid,
    quantity integer NOT NULL,
    purchase_price numeric,
    purchase_price_native numeric,
    purchase_date timestamp without time zone,
    created_at timestamp without time zone,
    CONSTRAINT asset_possession_quantity_check CHECK (((quantity <= 1000000000) AND (quantity >= 0)))
);

CREATE TABLE public.asset_valuations (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    valuation_date date NOT NULL,
    value_per_unit numeric NOT NULL,
    created_at timestamp without time zone NOT NULL
);

CREATE TABLE public.assets (
    user_id uuid,
    id uuid NOT NULL,
    symbol character varying(20) NOT NULL,
    name character varying(100) NOT NULL,
    asset_type character varying(20) NOT NULL,
    sector character varying(50),
    commodity_id uuid,
    value_per_unit numeric NOT NULL,
    track_live_price boolean NOT NULL,
    last_price_updated_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL,
    CONSTRAINT assets_asset_type_check CHECK (((asset_type)::text = ANY ((ARRAY['Stock'::character varying, 'ETF'::character varying, 'RealEstate'::character varying, 'Vehicle'::character varying, 'Other'::character varying])::text[]))),
    CONSTRAINT assets_check CHECK ((((asset_type)::text = ANY ((ARRAY['Stock'::character varying, 'ETF'::character varying])::text[])) OR (sector IS NULL))),
    CONSTRAINT assets_check1 CHECK (((track_live_price = false) OR ((asset_type)::text = ANY ((ARRAY['Stock'::character varying, 'ETF'::character varying])::text[]))))
);

CREATE TABLE public.budget_accounts (
    budget_id uuid NOT NULL,
    account_id uuid NOT NULL
);

CREATE TABLE public.budget_categories (
    budget_id uuid NOT NULL,
    category_id uuid NOT NULL
);

CREATE TABLE public.budget_tags (
    budget_id uuid NOT NULL,
    tag_id uuid NOT NULL
);

CREATE TABLE public.budgets (
    user_id uuid,
    id uuid NOT NULL,
    name character varying(100) NOT NULL,
    amount_allocated numeric NOT NULL,
    amount_spent numeric NOT NULL,
    start_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    amount_spent_incomplete boolean NOT NULL,
    renew_period character varying(16),
    renewed boolean NOT NULL
);

CREATE TABLE public.categories (
    id uuid NOT NULL,
    user_id uuid,
    name character varying(100) NOT NULL,
    description character varying(1000),
    created_at timestamp without time zone NOT NULL,
    tax_treatment character varying(32),
    CONSTRAINT ck_categories_tax_treatment CHECK ((((tax_treatment)::text = ANY ((ARRAY['taxable_income'::character varying, 'deductible'::character varying, 'real_estate_income'::character varying, 'real_estate_expense'::character varying])::text[])) OR (tax_treatment IS NULL)))
);

CREATE TABLE public.commodities (
    user_id uuid,
    id uuid NOT NULL,
    name character varying(128) NOT NULL,
    short_name character varying(6) NOT NULL,
    type character varying(8) NOT NULL,
    fraction smallint NOT NULL,
    description character varying(1024),
    track_live_rate boolean NOT NULL,
    last_rate_updated_at timestamp without time zone,
    created_at timestamp without time zone,
    CONSTRAINT commodities_type_check CHECK (((type)::text = ANY ((ARRAY['Currency'::character varying, 'Crypto'::character varying])::text[])))
);

CREATE TABLE public.custom_reports (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    config jsonb NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE public.financial_goals (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    name character varying(128) NOT NULL,
    goal_type character varying(16) NOT NULL,
    target_amount numeric NOT NULL,
    target_date timestamp without time zone NOT NULL,
    end_date timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT financial_goals_goal_type_check CHECK (((goal_type)::text = ANY ((ARRAY['one_time'::character varying, 'recurring'::character varying])::text[]))),
    CONSTRAINT financial_goals_target_amount_check CHECK ((target_amount > (0)::numeric))
);

CREATE TABLE public.fx_rates (
    id uuid NOT NULL,
    from_code character varying(10) NOT NULL,
    to_code character varying(10) NOT NULL,
    rate_date date NOT NULL,
    rate numeric NOT NULL,
    fetched_at timestamp without time zone
);

CREATE TABLE public.loan_installments (
    id uuid NOT NULL,
    loan_id uuid NOT NULL,
    installment_number integer NOT NULL,
    due_date date NOT NULL,
    principal_portion numeric NOT NULL,
    interest_portion numeric NOT NULL,
    insurance_portion numeric DEFAULT '0'::numeric NOT NULL,
    total_amount numeric NOT NULL,
    remaining_principal_after numeric NOT NULL,
    is_paid boolean DEFAULT false NOT NULL,
    paid_at timestamp without time zone,
    transaction_id uuid,
    rate_revision_id uuid,
    created_at timestamp without time zone
);

CREATE TABLE public.loan_rate_revisions (
    id uuid NOT NULL,
    loan_id uuid NOT NULL,
    effective_date date NOT NULL,
    new_annual_rate numeric NOT NULL,
    recalc_mode character varying(16) NOT NULL,
    created_at timestamp without time zone,
    CONSTRAINT loan_rate_revisions_recalc_mode_check CHECK (((recalc_mode)::text = ANY ((ARRAY['keep_term'::character varying, 'keep_payment'::character varying])::text[])))
);

CREATE TABLE public.loans (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    name character varying(128) NOT NULL,
    principal numeric NOT NULL,
    annual_rate numeric NOT NULL,
    term_months integer NOT NULL,
    start_date date NOT NULL,
    payment_day smallint NOT NULL,
    payment_account_id uuid NOT NULL,
    interest_expense_account_id uuid NOT NULL,
    insurance_expense_account_id uuid,
    insurance_monthly_amount numeric,
    liability_account_id uuid NOT NULL,
    equity_opening_account_id uuid,
    opening_transaction_id uuid,
    category_id uuid,
    auto_debit boolean DEFAULT false NOT NULL,
    is_existing_loan boolean DEFAULT false NOT NULL,
    is_closed boolean DEFAULT false NOT NULL,
    closed_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    CONSTRAINT loans_annual_rate_check CHECK ((annual_rate >= (0)::numeric)),
    CONSTRAINT loans_check CHECK (((is_existing_loan = false) OR (equity_opening_account_id IS NOT NULL))),
    CONSTRAINT loans_payment_day_check CHECK (((payment_day >= 1) AND (payment_day <= 31))),
    CONSTRAINT loans_principal_check CHECK ((principal > (0)::numeric)),
    CONSTRAINT loans_term_months_check CHECK ((term_months >= 1))
);

CREATE TABLE public.market_index (
    id uuid NOT NULL,
    index_name character varying(64) NOT NULL,
    ticker character varying(20) NOT NULL
);

CREATE TABLE public.permissions (
    id uuid NOT NULL,
    name character varying(50) NOT NULL,
    description character varying(250)
);

CREATE TABLE public.role_permissions (
    role_id uuid NOT NULL,
    permission_id uuid NOT NULL
);

CREATE TABLE public.roles (
    id uuid NOT NULL,
    name character varying(50) NOT NULL,
    description character varying(250),
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE public.splits (
    id uuid NOT NULL,
    tx_id uuid,
    quantity numeric NOT NULL,
    account_id uuid,
    is_reconciled boolean NOT NULL,
    description character varying(256),
    fx_rate numeric NOT NULL
);

CREATE TABLE public.subscriptions (
    user_id uuid,
    id uuid NOT NULL,
    name character varying(64) NOT NULL,
    schedule_type character varying(10) NOT NULL,
    day_of_month smallint,
    month_of_year smallint,
    weekdays character varying(20),
    amount numeric NOT NULL,
    from_account_id uuid,
    to_account_id uuid,
    category_id uuid,
    last_executed_at timestamp without time zone,
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    is_forecast_only boolean NOT NULL,
    CONSTRAINT subscriptions_schedule_type_check CHECK (((schedule_type)::text = ANY ((ARRAY['monthly'::character varying, 'yearly'::character varying, 'weekly'::character varying])::text[])))
);

CREATE TABLE public.tags (
    id uuid NOT NULL,
    user_id uuid,
    name character varying(100) NOT NULL,
    color character varying(64) NOT NULL,
    created_at timestamp without time zone NOT NULL,
    tax_treatment character varying(32),
    CONSTRAINT ck_tags_tax_treatment CHECK ((((tax_treatment)::text = ANY ((ARRAY['taxable_income'::character varying, 'deductible'::character varying, 'real_estate_income'::character varying, 'real_estate_expense'::character varying])::text[])) OR (tax_treatment IS NULL))),
    CONSTRAINT tags_color_check CHECK (((color)::text = ANY ((ARRAY['green'::character varying, 'red'::character varying, 'blue'::character varying, 'white'::character varying, 'black'::character varying, 'yellow'::character varying, 'purple'::character varying])::text[])))
);

CREATE TABLE public.tags_on_split (
    split_id uuid NOT NULL,
    tag_id uuid NOT NULL
);

CREATE TABLE public.tax_household_income (
    id uuid NOT NULL,
    household_profile_id uuid NOT NULL,
    label character varying(200) NOT NULL,
    amount numeric NOT NULL,
    income_type character varying(32) NOT NULL,
    created_at timestamp without time zone
);

CREATE TABLE public.tax_household_profile (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    tax_year integer NOT NULL,
    adults integer NOT NULL,
    dependents integer NOT NULL,
    dependents_disabled integer NOT NULL,
    parent_isole boolean NOT NULL,
    notes character varying(1000),
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE public.tax_regime (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    name character varying(100) NOT NULL,
    country_code character varying(2) NOT NULL,
    tax_year integer NOT NULL,
    config jsonb NOT NULL,
    is_active boolean NOT NULL,
    is_verified boolean NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE public.transaction_documents (
    id uuid NOT NULL,
    tx_id uuid,
    user_id uuid NOT NULL,
    original_filename character varying(256) NOT NULL,
    mime_type character varying(100) NOT NULL,
    file_data bytea NOT NULL,
    status character varying(20) NOT NULL,
    uploaded_at timestamp without time zone NOT NULL,
    CONSTRAINT transaction_documents_status_check CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'confirmed'::character varying])::text[])))
);

CREATE TABLE public.transactions (
    user_id uuid,
    id uuid NOT NULL,
    currency_id uuid,
    post_date timestamp without time zone NOT NULL,
    effective_date timestamp without time zone NOT NULL,
    description character varying(1024),
    category_id uuid,
    is_cleared boolean NOT NULL
);

CREATE TABLE public.user_roles (
    user_id uuid NOT NULL,
    role_id uuid NOT NULL
);

CREATE TABLE public.user_settings (
    user_id uuid NOT NULL,
    currency character varying(6) NOT NULL,
    date_format character varying(16) NOT NULL,
    market_score_weights jsonb,
    market_score_thresholds jsonb,
    updated_at timestamp without time zone,
    onboarding_completed boolean NOT NULL
);

CREATE TABLE public.users (
    id uuid NOT NULL,
    username character varying(50) NOT NULL,
    email character varying(100) NOT NULL,
    password_hash bytea NOT NULL,
    salt bytea NOT NULL,
    created_at timestamp without time zone,
    updated_at timestamp without time zone
);

CREATE TABLE public.watchlist (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    ticker character varying(20) NOT NULL,
    added_at timestamp without time zone NOT NULL
);

CREATE TABLE public.wealth_snapshot (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    snapshot_date date NOT NULL,
    bank_net_worth numeric NOT NULL,
    portfolio_value numeric NOT NULL,
    total numeric NOT NULL,
    created_at timestamp without time zone NOT NULL
);

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_name_key UNIQUE (user_id, name);

ALTER TABLE ONLY public.asset_disposal
    ADD CONSTRAINT asset_disposal_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.asset_valuations
    ADD CONSTRAINT asset_valuations_asset_id_valuation_date_key UNIQUE (asset_id, valuation_date);

ALTER TABLE ONLY public.asset_valuations
    ADD CONSTRAINT asset_valuations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_name_asset_type_commodity_id_key UNIQUE (name, asset_type, commodity_id);

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.budget_accounts
    ADD CONSTRAINT budget_accounts_pkey PRIMARY KEY (budget_id, account_id);

ALTER TABLE ONLY public.budget_categories
    ADD CONSTRAINT budget_categories_pkey PRIMARY KEY (budget_id, category_id);

ALTER TABLE ONLY public.budget_tags
    ADD CONSTRAINT budget_tags_pkey PRIMARY KEY (budget_id, tag_id);

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT budgets_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_user_id_name_key UNIQUE (user_id, name);

ALTER TABLE ONLY public.commodities
    ADD CONSTRAINT commodities_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.commodities
    ADD CONSTRAINT commodities_user_id_short_name_key UNIQUE (user_id, short_name);

ALTER TABLE ONLY public.custom_reports
    ADD CONSTRAINT custom_reports_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.financial_goals
    ADD CONSTRAINT financial_goals_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.fx_rates
    ADD CONSTRAINT fx_rates_from_code_to_code_rate_date_key UNIQUE (from_code, to_code, rate_date);

ALTER TABLE ONLY public.fx_rates
    ADD CONSTRAINT fx_rates_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_loan_id_installment_number_key UNIQUE (loan_id, installment_number);

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.loan_rate_revisions
    ADD CONSTRAINT loan_rate_revisions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_user_id_name_key UNIQUE (user_id, name);

ALTER TABLE ONLY public.market_index
    ADD CONSTRAINT market_index_index_name_ticker_key UNIQUE (index_name, ticker);

ALTER TABLE ONLY public.market_index
    ADD CONSTRAINT market_index_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_id);

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.splits
    ADD CONSTRAINT splits_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_user_id_name_key UNIQUE (user_id, name);

ALTER TABLE ONLY public.tags_on_split
    ADD CONSTRAINT tags_on_split_pkey PRIMARY KEY (split_id, tag_id);

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_user_id_name_key UNIQUE (user_id, name);

ALTER TABLE ONLY public.tax_household_income
    ADD CONSTRAINT tax_household_income_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tax_household_profile
    ADD CONSTRAINT tax_household_profile_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tax_household_profile
    ADD CONSTRAINT tax_household_profile_user_id_tax_year_key UNIQUE (user_id, tax_year);

ALTER TABLE ONLY public.tax_regime
    ADD CONSTRAINT tax_regime_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tax_regime
    ADD CONSTRAINT tax_regime_user_id_name_key UNIQUE (user_id, name);

ALTER TABLE ONLY public.transaction_documents
    ADD CONSTRAINT transaction_documents_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_pkey PRIMARY KEY (user_id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.watchlist
    ADD CONSTRAINT watchlist_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.watchlist
    ADD CONSTRAINT watchlist_user_id_ticker_key UNIQUE (user_id, ticker);

ALTER TABLE ONLY public.wealth_snapshot
    ADD CONSTRAINT wealth_snapshot_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.wealth_snapshot
    ADD CONSTRAINT wealth_snapshot_user_id_snapshot_date_key UNIQUE (user_id, snapshot_date);

CREATE INDEX ix_loan_installments_loan_due ON public.loan_installments USING btree (loan_id, due_date);

CREATE INDEX ix_loan_installments_loan_paid ON public.loan_installments USING btree (loan_id, is_paid);

CREATE UNIQUE INDEX ix_permissions_name ON public.permissions USING btree (name);

CREATE UNIQUE INDEX ix_roles_name ON public.roles USING btree (name);

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);

CREATE TRIGGER trg_check_category_id BEFORE INSERT OR UPDATE ON public.transactions FOR EACH ROW EXECUTE FUNCTION public.check_category_id();

CREATE TRIGGER trg_handle_account_parent_change AFTER INSERT OR DELETE OR UPDATE OF parent_id ON public.accounts FOR EACH ROW EXECUTE FUNCTION public.handle_account_parent_change();

CREATE TRIGGER trg_update_account_totals AFTER INSERT OR DELETE OR UPDATE ON public.splits FOR EACH ROW EXECUTE FUNCTION public.update_account_totals();

CREATE TRIGGER trg_update_budget_spent AFTER INSERT OR DELETE OR UPDATE ON public.splits FOR EACH ROW EXECUTE FUNCTION public.update_budget_spent();

CREATE TRIGGER trg_update_timestamp_accounts BEFORE UPDATE ON public.accounts FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();

CREATE TRIGGER trg_update_timestamp_budgets BEFORE UPDATE ON public.budgets FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();

CREATE TRIGGER trg_update_timestamp_users BEFORE UPDATE ON public.users FOR EACH ROW EXECUTE FUNCTION public.update_timestamp();

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES public.commodities(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.asset_disposal
    ADD CONSTRAINT asset_disposal_dest_account_id_fkey FOREIGN KEY (dest_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_disposal
    ADD CONSTRAINT asset_disposal_dest_split_id_fkey FOREIGN KEY (dest_split_id) REFERENCES public.splits(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_disposal
    ADD CONSTRAINT asset_disposal_possession_id_fkey FOREIGN KEY (possession_id) REFERENCES public.asset_possession(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.asset_disposal
    ADD CONSTRAINT asset_disposal_source_split_id_fkey FOREIGN KEY (source_split_id) REFERENCES public.splits(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_disposal
    ADD CONSTRAINT asset_disposal_tx_id_fkey FOREIGN KEY (tx_id) REFERENCES public.transactions(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_disposal
    ADD CONSTRAINT asset_disposal_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_dest_split_id_fkey FOREIGN KEY (dest_split_id) REFERENCES public.splits(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_source_account_id_fkey FOREIGN KEY (source_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_source_split_id_fkey FOREIGN KEY (source_split_id) REFERENCES public.splits(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_tx_id_fkey FOREIGN KEY (tx_id) REFERENCES public.transactions(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.asset_possession
    ADD CONSTRAINT asset_possession_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.asset_valuations
    ADD CONSTRAINT asset_valuations_asset_id_fkey FOREIGN KEY (asset_id) REFERENCES public.assets(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.asset_valuations
    ADD CONSTRAINT asset_valuations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_commodity_id_fkey FOREIGN KEY (commodity_id) REFERENCES public.commodities(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.assets
    ADD CONSTRAINT assets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_accounts
    ADD CONSTRAINT budget_accounts_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_accounts
    ADD CONSTRAINT budget_accounts_budget_id_fkey FOREIGN KEY (budget_id) REFERENCES public.budgets(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_categories
    ADD CONSTRAINT budget_categories_budget_id_fkey FOREIGN KEY (budget_id) REFERENCES public.budgets(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_categories
    ADD CONSTRAINT budget_categories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_tags
    ADD CONSTRAINT budget_tags_budget_id_fkey FOREIGN KEY (budget_id) REFERENCES public.budgets(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budget_tags
    ADD CONSTRAINT budget_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.budgets
    ADD CONSTRAINT budgets_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.commodities
    ADD CONSTRAINT commodities_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.custom_reports
    ADD CONSTRAINT custom_reports_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.financial_goals
    ADD CONSTRAINT financial_goals_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_loan_id_fkey FOREIGN KEY (loan_id) REFERENCES public.loans(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_rate_revision_id_fkey FOREIGN KEY (rate_revision_id) REFERENCES public.loan_rate_revisions(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.loan_installments
    ADD CONSTRAINT loan_installments_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.transactions(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.loan_rate_revisions
    ADD CONSTRAINT loan_rate_revisions_loan_id_fkey FOREIGN KEY (loan_id) REFERENCES public.loans(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_equity_opening_account_id_fkey FOREIGN KEY (equity_opening_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_insurance_expense_account_id_fkey FOREIGN KEY (insurance_expense_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_interest_expense_account_id_fkey FOREIGN KEY (interest_expense_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_liability_account_id_fkey FOREIGN KEY (liability_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_opening_transaction_id_fkey FOREIGN KEY (opening_transaction_id) REFERENCES public.transactions(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_payment_account_id_fkey FOREIGN KEY (payment_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.loans
    ADD CONSTRAINT loans_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES public.permissions(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.splits
    ADD CONSTRAINT splits_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public.splits
    ADD CONSTRAINT splits_tx_id_fkey FOREIGN KEY (tx_id) REFERENCES public.transactions(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_from_account_id_fkey FOREIGN KEY (from_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_to_account_id_fkey FOREIGN KEY (to_account_id) REFERENCES public.accounts(id) ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tags_on_split
    ADD CONSTRAINT tags_on_split_split_id_fkey FOREIGN KEY (split_id) REFERENCES public.splits(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tags_on_split
    ADD CONSTRAINT tags_on_split_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tax_household_income
    ADD CONSTRAINT tax_household_income_household_profile_id_fkey FOREIGN KEY (household_profile_id) REFERENCES public.tax_household_profile(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tax_household_profile
    ADD CONSTRAINT tax_household_profile_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.tax_regime
    ADD CONSTRAINT tax_regime_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.transaction_documents
    ADD CONSTRAINT transaction_documents_tx_id_fkey FOREIGN KEY (tx_id) REFERENCES public.transactions(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.transaction_documents
    ADD CONSTRAINT transaction_documents_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id) ON UPDATE CASCADE ON DELETE SET NULL;

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_currency_id_fkey FOREIGN KEY (currency_id) REFERENCES public.commodities(id) ON UPDATE CASCADE ON DELETE CASCADE;

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.watchlist
    ADD CONSTRAINT watchlist_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.wealth_snapshot
    ADD CONSTRAINT wealth_snapshot_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;
"""
