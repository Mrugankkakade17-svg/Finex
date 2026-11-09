-- =====================================================================
-- Task: S1-DAT-01
-- Catalog: finex_dev
-- Schema: core
-- Purpose: Operational, user-owned records
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS finex_dev.core;

-- ---------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.users (
    user_id         BIGINT GENERATED ALWAYS AS IDENTITY,
    email           STRING NOT NULL,
    password_hash   STRING NOT NULL,
    name            STRING NOT NULL,
    role            STRING,
    risk_profile    STRING,
    is_active       BOOLEAN,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- user_profiles
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.user_profiles (
    profile_id      BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id         BIGINT NOT NULL,
    first_name      STRING,
    last_name       STRING,
    phone           STRING,
    date_of_birth   DATE,
    address         STRING,
    city            STRING,
    country         STRING,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- portfolios
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.portfolios (
    portfolio_id    BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id         BIGINT NOT NULL,
    name            STRING NOT NULL,
    description     STRING,
    portfolio_type  STRING,
    total_value     DOUBLE,
    is_active       BOOLEAN,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- portfolio_holdings
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.portfolio_holdings (
    holding_id      BIGINT GENERATED ALWAYS AS IDENTITY,
    portfolio_id    BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    instrument_id   BIGINT NOT NULL,
    quantity        DOUBLE NOT NULL,
    avg_buy_price   DOUBLE NOT NULL,
    current_value   DOUBLE,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- transactions
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.transactions (
    transaction_id      BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id              BIGINT NOT NULL,
    portfolio_id         BIGINT NOT NULL,
    instrument_id        BIGINT NOT NULL,
    transaction_type     STRING NOT NULL,
    quantity              DOUBLE NOT NULL,
    price                  DOUBLE NOT NULL,
    total_amount          DOUBLE NOT NULL,
    status                 STRING,
    created_at             TIMESTAMP
);

-- ---------------------------------------------------------------------
-- paper_trades
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.paper_trades (
    trade_id        BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id         BIGINT NOT NULL,
    instrument_id   BIGINT NOT NULL,
    trade_type      STRING NOT NULL,
    quantity        DOUBLE NOT NULL,
    entry_price     DOUBLE NOT NULL,
    exit_price      DOUBLE,
    pnl             DOUBLE,
    status          STRING,
    created_at      TIMESTAMP,
    closed_at       TIMESTAMP
);

-- ---------------------------------------------------------------------
-- goals
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.goals (
    goal_id         BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id         BIGINT NOT NULL,
    name            STRING NOT NULL,
    target_amount   DOUBLE NOT NULL,
    current_amount  DOUBLE,
    deadline        DATE,
    status          STRING,
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- risk_profiles
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.risk_profiles (
    risk_id          BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id          BIGINT NOT NULL,
    risk_score       INT,
    risk_category    STRING,
    assessment_date  TIMESTAMP,
    factors          STRING,
    created_at       TIMESTAMP,
    updated_at       TIMESTAMP
);

-- ---------------------------------------------------------------------
-- alerts
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.core.alerts (
    alert_id        BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id         BIGINT NOT NULL,
    alert_type      STRING NOT NULL,
    title           STRING NOT NULL,
    message         STRING,
    is_read         BOOLEAN,
    priority        STRING,
    created_at      TIMESTAMP
);
