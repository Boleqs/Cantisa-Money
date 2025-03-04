-- noinspection SqlNoDataSourceInspectionForFile

-- Partie gestion des users / sécurité de l'app

CREATE TABLE users (
    id              CHAR(36) PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    email           VARCHAR(100) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Index pour optimiser les recherches
CREATE INDEX idx_username ON users (username);
CREATE INDEX idx_email ON users (email);


-- Partie gestion comptabilité

CREATE TABLE commodities (
    user_id     CHAR(36),
    id          CHAR(36),
    name        VARCHAR(128) NOT NULL,
    short_name  VARCHAR(6) NULL UNIQUE,
    type        VARCHAR(8) NOT NULL DEFAULT 'Currency' CHECK (type in ('Currency', 'Crypto')),
    fraction    SMALLINT DEFAULT 2 NOT NULL,
    description VARCHAR(1024) NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- clé primaire
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, short_name),
    -- clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE accounts (
    user_id      CHAR(36),
    id           CHAR(36),
    name         VARCHAR(128) NOT NULL,
    parent_id    CHAR(36) NULL,
    account_type VARCHAR(64) NOT NULL DEFAULT 'Current' CHECK (account_type IN ('Income', 'Expense', 'Equity', 'Assets', 'Current')),
    -- account_subtype uniquement rempli si account_type = Equity
    account_subtype VARCHAR(64) NULL CHECK ((account_type = 'Equity' and account_subtype IN ('fr_PEA', 'Other')) OR account_subtype is NULL),
    currency_id  CHAR(36) NOT NULL,
    description  VARCHAR(1024) NULL,
    is_virtual   BOOLEAN DEFAULT FALSE NOT NULL,
    is_hidden    BOOLEAN DEFAULT FALSE NOT NULL,
    code         VARCHAR(64) NULL,
	created_at   DATE DEFAULT CURRENT_DATE,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- clé primaire
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, name),
    -- clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (currency_id) REFERENCES commodities(id) ON UPDATE CASCADE
);
-- Index pour optimiser les recherches
CREATE INDEX idx_currency_id ON accounts (currency_id);


CREATE TABLE transactions (
    user_id        CHAR(36),
    id             CHAR(36),
    currency_id    CHAR(36) NOT NULL,
    post_date 	   DATE DEFAULT CURRENT_DATE,
    effective_date DATE DEFAULT CURRENT_DATE,
    description    VARCHAR(1024) NULL,
    category_id    CHAR(36) NOT NULL DEFAULT 'N/A' CHECK (category_id IN (SELECT name from categories where categories.user_id = transactions.user_id)),

    -- clé primaire
    PRIMARY KEY (user_id, id),
    -- clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (currency_id) REFERENCES commodities(id) ON UPDATE CASCADE
);


CREATE TABLE splits (
    id         CHAR(36) PRIMARY KEY,
    tx_id      CHAR(36) NOT NULL,
    quantity   INT NOT NULL,
    account_id CHAR(36) NOT NULL,
    FOREIGN KEY (tx_id) REFERENCES transactions(id) ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(name) ON UPDATE CASCADE ON DELETE CASCADE
);
-- Index pour optimiser les recherches
CREATE INDEX idx_account_id ON splits (account_id);
CREATE INDEX idx_tx_id ON splits (tx_id);
CREATE INDEX idx_currency_id ON transactions (currency_id);


CREATE TABLE categories (
    user_id     CHAR(36),
    id          CHAR(36),
    name        VARCHAR(64) UNIQUE NOT NULL,
    description VARCHAR(255) NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- clé primaire
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, name),
    -- clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id)
);
-- Index pour accélérer la recherche par nom
CREATE INDEX idx_category_name ON categories (name);

CREATE TABLE subscriptions (
    user_id     CHAR(36),
    id          CHAR(36),
    name        VARCHAR(64) UNIQUE NOT NULL,
    recurrence  SMALLINT NOT NULL DEFAULT 30,
    amount      INT NOT NULL DEFAULT 0,
    account_id  CHAR(36),
    category_id CHAR(36),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- clé primaire
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, name),
    -- clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (account_id) REFERENCES accounts (id),
    FOREIGN KEY (category_id) REFERENCES categories (id)

);

CREATE TABLE tags (
    user_id     CHAR(36),
    id          CHAR(36),
    name        VARCHAR(64) UNIQUE NOT NULL,
    color       VARCHAR(10) DEFAULT 'green' CHECK (color in ('green', 'red', 'blue', 'white', 'black', 'yellow', 'purple')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- clé primaire
    PRIMARY KEY (user_id, id),
    UNIQUE (user_id, name),
    -- clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE tags_on_split (
    split_id    CHAR(36) NOT NULL,
    tag_id      CHAR(36) NOT NULL,
    -- clé unique
    UNIQUE (split_id, tag_id),
    -- clés étrangères
    FOREIGN KEY (split_id) REFERENCES splits (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

-- Partie gestion Finances

CREATE TABLE assets (
    user_id       CHAR(36),
    id            CHAR(36),
    symbol        VARCHAR(20) UNIQUE NOT NULL,
    name          VARCHAR(100) NOT NULL,
    asset_type    VARCHAR(20) NOT NULL CHECK (asset_type IN ('Stock', 'ETF', 'RealEstate', 'Vehicle', 'Other')),
    sector        VARCHAR(50) NULL CHECK (asset_type = ('Stock' OR 'ETF') OR sector is NULL), -- Secteur pour les actions/ETFs
    commodity     VARCHAR(6) NOT NULL,
    value_per_unit         INT NOT NULL DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- clé primaire
    PRIMARY KEY (user_id, id),
    UNIQUE (name, asset_type, commodity),
    -- clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (commodity) REFERENCES commodities (short_name)
);

CREATE TABLE asset_possession (
    user_id       CHAR(36),
    id            CHAR(36) UNIQUE,
    asset_id      CHAR(36) NOT NULL,
    account_id    CHAR(36) NOT NULL,
    quantity      INT NOT NULL DEFAULT 0 CHECK (quantity <= 1000000000 AND quantity >= 0),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- clé primaire
    PRIMARY KEY (user_id, id),
    -- clés étrangères
    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (account_id) REFERENCES accounts (name)
);


-- Partie gestion Stats

CREATE TABLE budgets (
    user_id         CHAR(36),
    id              CHAR(36) UNIQUE,
    amount_allocated INT NOT NULL CHECK (amount_allocated >= 0),
    amount_spent    INT DEFAULT 0 CHECK (amount_spent >= 0),
    start_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    end_date        DATE NOT NULL DEFAULT (CURRENT_DATE + INTERVAL '365 days') CHECK (end_date >= start_date),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    -- clé primaire
    PRIMARY KEY (user_id, id),
    -- Clés étrangères
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
-- Index pour optimiser les recherches
CREATE INDEX idx_user_id ON budgets (user_id);
CREATE INDEX idx_start_date ON budgets (start_date);
CREATE INDEX idx_end_date ON budgets (end_date);


CREATE TABLE budget_accounts (
    budget_id       CHAR(36) NOT NULL,
    account_id      CHAR(36) NOT NULL,

    -- clé unique
    UNIQUE (budget_id, account_id),
    -- Clés étrangères
    FOREIGN KEY (budget_id) REFERENCES  budgets (id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts (name) ON DELETE CASCADE
);


CREATE TABLE budget_categories (
    budget_id       CHAR(36) NOT NULL,
    category_id      CHAR(36) NOT NULL,

    -- clé unique
    UNIQUE (budget_id, category_id),
    -- Clés étrangères
    FOREIGN KEY (budget_id) REFERENCES  budgets (id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
);

CREATE TABLE budget_tags (
    budget_id    CHAR(36) NOT NULL,
    tag_id      CHAR(36) NOT NULL,
    -- clé unique
    UNIQUE (budget_id, tag_id),
    -- clés étrangères
    FOREIGN KEY (budget_id) REFERENCES budgets (id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
);


-- Triggers

-- Auto update budget spent

CREATE OR REPLACE FUNCTION update_budget_spent()
RETURNS TRIGGER AS $$
DECLARE
    total_spent INT;
BEGIN
    -- Calculer le total des transactions liées aux comptes associés au budget
    SELECT COALESCE(SUM(s.quantity), 0) INTO total_spent
    FROM splits s
    WHERE s.account_id IN (
        SELECT account_id FROM budget_accounts WHERE budget_id = NEW.id
    );

    -- Ajouter les transactions liées aux catégories associées au budget
    SELECT COALESCE(total_spent + SUM(s.quantity), total_spent) INTO total_spent
    FROM splits s
    JOIN transactions t ON s.tx_id = t.id
    WHERE t.category_id IN (
        SELECT category_id FROM budget_categories WHERE budget_id = NEW.id
    );

    -- Ajouter les transactions liées aux tags associés au budget
    SELECT COALESCE(total_spent + SUM(s.quantity), total_spent) INTO total_spent
    FROM splits s
    JOIN tags_on_split ts ON s.id = ts.split_id
    WHERE ts.tag_id IN (
        SELECT tag_id FROM budget_tags WHERE budget_id = NEW.id
    );

    -- Mettre à jour le montant dépensé dans le budget
    UPDATE budgets
    SET amount_spent = total_spent
    WHERE id = NEW.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_budget_changes
BEFORE UPDATE ON budgets
FOR EACH ROW
EXECUTE FUNCTION update_budget_spent();

-- Auto update fields updated_at

CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_timestamp
BEFORE UPDATE ON accounts
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_update_timestamp
BEFORE UPDATE ON budgets
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();

CREATE TRIGGER trg_update_timestamp
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION update_timestamp();