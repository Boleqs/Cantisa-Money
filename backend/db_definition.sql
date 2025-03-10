create table users
(
    id            varchar(36)  not null
        primary key,
    username      varchar(50)  not null,
    email         varchar(100) not null,
    password_hash varchar(255) not null,
    created_at    timestamp,
    updated_at    timestamp
);

create unique index ix_users_email
    on users (email);

create index ix_users_username
    on users (username);

create table budgets
(
    user_id          varchar(36)
        references users
            on delete cascade,
    id               varchar(36) not null
        primary key,
    amount_allocated numeric     not null,
    amount_spent     numeric     not null,
    start_date       timestamp   not null,
    end_date         timestamp   not null,
    created_at       timestamp,
    updated_at       timestamp
);

create table categories
(
    id          varchar(36)  not null
        primary key,
    user_id     varchar(36)  not null
        references users
            on delete cascade,
    name        varchar(100) not null
        unique,
    description varchar(1000),
    created_at  timestamp    not null,
    unique (user_id, name)
);

create table commodities
(
    user_id     varchar(36)  not null
        references users
            on delete cascade,
    id          varchar(36)  not null
        primary key,
    name        varchar(128) not null,
    short_name  varchar(6)   not null,
    type        varchar(8)   not null
        constraint commodities_type_check
            check ((type)::text = ANY ((ARRAY ['Currency'::character varying, 'Crypto'::character varying])::text[])),
    fraction    smallint     not null,
    description varchar(1024),
    created_at  timestamp,
    unique (user_id, short_name)
);

create table tags
(
    id         varchar(36)  not null
        primary key,
    user_id    varchar(36)  not null
        references users
            on delete cascade,
    name       varchar(100) not null,
    color      varchar(64)  not null
        constraint tags_color_check
            check ((color)::text = ANY
                   ((ARRAY ['green'::character varying, 'red'::character varying, 'blue'::character varying, 'white'::character varying, 'black'::character varying, 'yellow'::character varying, 'purple'::character varying])::text[])),
    created_at timestamp    not null,
    unique (user_id, name)
);

create table accounts
(
    user_id         varchar(36)  not null
        references users
            on delete cascade,
    id              varchar(36)  not null
        primary key,
    name            varchar(128) not null,
    parent_id       varchar(36),
    account_type    varchar(64)  not null
        constraint accounts_account_type_check
            check ((account_type)::text = ANY
                   ((ARRAY ['Income'::character varying, 'Expense'::character varying, 'Equity'::character varying, 'Assets'::character varying, 'Current'::character varying])::text[])),
    account_subtype varchar(64),
    currency_id     varchar(36)  not null
        references commodities
            on delete cascade,
    description     varchar(1024),
    total_spent     numeric      not null,
    total_earned    numeric      not null,
    is_virtual      boolean      not null,
    is_hidden       boolean      not null,
    code            varchar(64),
    created_at      timestamp,
    updated_at      timestamp,
    unique (user_id, name),
    constraint accounts_check
        check ((((account_type)::text = 'Equity'::text) AND ((account_subtype)::text = ANY
                                                             ((ARRAY ['fr_PEA'::character varying, 'Other'::character varying])::text[]))) OR
               (account_subtype IS NULL))
);

create table assets
(
    user_id        varchar(36)
        references users
            on delete cascade,
    id             varchar(36)  not null
        primary key,
    symbol         varchar(20)  not null,
    name           varchar(100) not null,
    asset_type     varchar(20)  not null
        constraint assets_asset_type_check
            check ((asset_type)::text = ANY
                   ((ARRAY ['Stock'::character varying, 'ETF'::character varying, 'RealEstate'::character varying, 'Vehicle'::character varying, 'Other'::character varying])::text[])),
    sector         varchar(50),
    commodity_id   varchar(6)   not null
        references commodities
            on delete cascade,
    value_per_unit numeric      not null,
    created_at     timestamp    not null,
    unique (name, asset_type, commodity_id),
    constraint assets_check
        check (((asset_type)::text = ANY ((ARRAY ['Stock'::character varying, 'ETF'::character varying])::text[])) OR
               (sector IS NULL))
);

create table budget_categories
(
    budget_id   varchar(36) not null
        references budgets
            on delete cascade,
    category_id varchar(36) not null
        references categories
            on delete cascade,
    primary key (budget_id, category_id)
);

create table budget_tags
(
    budget_id varchar(36) not null
        references budgets
            on delete cascade,
    tag_id    varchar(36) not null
        references tags
            on delete cascade,
    primary key (budget_id, tag_id)
);

create table transactions
(
    user_id        varchar(36)
        references users
            on delete cascade,
    id             varchar(36) not null
        primary key,
    currency_id    varchar(36) not null
        references commodities
            on update cascade on delete cascade,
    post_date      timestamp   not null,
    effective_date timestamp   not null,
    description    varchar(1024),
    category_id    varchar(36) not null
);

create table asset_possession
(
    user_id    varchar(36) not null
        references users
            on delete cascade,
    id         varchar(36) not null
        primary key,
    asset_id   varchar(36) not null
        references assets
            on delete cascade,
    account_id varchar(36) not null
        references accounts
            on update cascade on delete cascade,
    quantity   integer     not null
        constraint asset_possession_quantity_check
            check ((quantity <= 1000000000) AND (quantity >= 0)),
    created_at timestamp
);

create table budget_accounts
(
    budget_id  varchar(36) not null
        references budgets
            on delete cascade,
    account_id varchar(36) not null
        references accounts
            on delete cascade,
    primary key (budget_id, account_id)
);

create table splits
(
    id         varchar(36) not null
        primary key,
    tx_id      varchar(36) not null
        references transactions
            on update cascade on delete cascade,
    quantity   numeric     not null,
    account_id varchar(36) not null
        references accounts
            on update cascade on delete cascade
);

create table subscriptions
(
    user_id     varchar(36) not null
        references users
            on delete cascade,
    id          varchar(36) not null
        primary key,
    name        varchar(64) not null,
    recurrence  smallint    not null,
    amount      numeric     not null,
    account_id  varchar(36) not null
        references accounts
            on update cascade on delete cascade,
    category_id varchar(36) not null
        references categories
            on update cascade on delete cascade,
    created_at  timestamp,
    unique (user_id, name)
);

create table tags_on_split
(
    split_id varchar(36) not null
        references splits
            on delete cascade,
    tag_id   varchar(36) not null
        references tags
            on delete cascade,
    primary key (split_id, tag_id)
);

create function check_category_id() returns trigger
    language plpgsql
as
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM categories WHERE id = NEW.category_id AND user_id = NEW.user_id) THEN
        RAISE EXCEPTION 'Invalid category_id % for user_id %', NEW.category_id, NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$;

create trigger trg_check_category_id
    before insert or update
    on transactions
    for each row
execute procedure check_category_id();

create function update_budget_spent() returns trigger
    language plpgsql
as
$$
DECLARE
    total_spent INT;
BEGIN
    -- Calculer le total des transactions liées aux comptes associés au budget
    SELECT COALESCE(SUM(s.quantity), 0) INTO total_spent
    FROM splits s
    WHERE s.account_id IN (
        -- SELECT account_id FROM budget_accounts WHERE budget_id = NEW.id
        SELECT account_id FROM budget_accounts WHERE budget_id = NEW.budget_id --ia
    );

    -- Ajouter les transactions liées aux catégories associées au budget
    SELECT COALESCE(total_spent + SUM(s.quantity), total_spent) INTO total_spent
    FROM splits s
    JOIN transactions t ON s.tx_id = t.id
    WHERE t.category_id IN (
        -- SELECT category_id FROM budget_categories WHERE budget_id = NEW.id
        SELECT category_id FROM budget_categories WHERE budget_id = NEW.budget_id --ia
    );

    -- Ajouter les transactions liées aux tags associés au budget
    SELECT COALESCE(total_spent + SUM(s.quantity), total_spent) INTO total_spent
    FROM splits s
    JOIN tags_on_split ts ON s.id = ts.split_id
    WHERE ts.tag_id IN (
        -- SELECT tag_id FROM budget_tags WHERE budget_id = NEW.id 
        SELECT tag_id FROM budget_tags WHERE budget_id = NEW.budget_id --ia
    );

    -- Mettre à jour le montant dépensé dans le budget
    UPDATE budgets
    SET amount_spent = total_spent
    -- WHERE id = NEW.id;
    WHERE id = NEW.budget_id; -- ia

    RETURN NEW;
END;
$$;

create trigger trg_update_budget_spent
    after insert or update
    on splits
    for each row
execute procedure update_budget_spent();

create function update_timestamp() returns trigger
    language plpgsql
as
$$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

create trigger trg_update_timestamp_users
    before update
    on users
    for each row
execute procedure update_timestamp();

create trigger trg_update_timestamp_budgets
    before update
    on budgets
    for each row
execute procedure update_timestamp();

create trigger trg_update_timestamp_accounts
    before update
    on accounts
    for each row
execute procedure update_timestamp();

