-- =====================================================================
-- FinEx Databricks Catalog & Schema Creation Notebook
-- Task: S1-DAT-01
-- Owner: Shivraj
-- Run this notebook to set up finex_dev catalog with all schemas/tables
-- =====================================================================

-- Create catalog
CREATE CATALOG IF NOT EXISTS finex_dev;

-- =====================================================================
-- SCHEMA: core
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS finex_dev.core;

CREATE TABLE IF NOT EXISTS finex_dev.core.users (
    user_id BIGINT GENERATED ALWAYS AS IDENTITY, email STRING NOT NULL,
    password_hash STRING NOT NULL, name STRING NOT NULL, role STRING,
    risk_profile STRING, is_active BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.user_profiles (
    profile_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    first_name STRING, last_name STRING, phone STRING, date_of_birth DATE,
    address STRING, city STRING, country STRING, created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.portfolios (
    portfolio_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    name STRING NOT NULL, description STRING, portfolio_type STRING,
    total_value DOUBLE, is_active BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.portfolio_holdings (
    holding_id BIGINT GENERATED ALWAYS AS IDENTITY, portfolio_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL, instrument_id BIGINT NOT NULL, quantity DOUBLE NOT NULL,
    avg_buy_price DOUBLE NOT NULL, current_value DOUBLE, created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.transactions (
    transaction_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    portfolio_id BIGINT NOT NULL, instrument_id BIGINT NOT NULL, transaction_type STRING NOT NULL,
    quantity DOUBLE NOT NULL, price DOUBLE NOT NULL, total_amount DOUBLE NOT NULL,
    status STRING, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.paper_trades (
    trade_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    instrument_id BIGINT NOT NULL, trade_type STRING NOT NULL, quantity DOUBLE NOT NULL,
    entry_price DOUBLE NOT NULL, exit_price DOUBLE, pnl DOUBLE, status STRING,
    created_at TIMESTAMP, closed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.goals (
    goal_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    name STRING NOT NULL, target_amount DOUBLE NOT NULL, current_amount DOUBLE,
    deadline DATE, status STRING, created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.risk_profiles (
    risk_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    risk_score INT, risk_category STRING, assessment_date TIMESTAMP, factors STRING,
    created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.core.alerts (
    alert_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    alert_type STRING NOT NULL, title STRING NOT NULL, message STRING,
    is_read BOOLEAN, priority STRING, created_at TIMESTAMP
);

-- =====================================================================
-- SCHEMA: market
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS finex_dev.market;

CREATE TABLE IF NOT EXISTS finex_dev.market.instruments (
    instrument_id BIGINT GENERATED ALWAYS AS IDENTITY, symbol STRING NOT NULL,
    name STRING NOT NULL, instrument_type STRING NOT NULL, exchange STRING,
    sector STRING, is_active BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.market.prices (
    price_id BIGINT GENERATED ALWAYS AS IDENTITY, instrument_id BIGINT NOT NULL,
    open_price DOUBLE, high_price DOUBLE, low_price DOUBLE, close_price DOUBLE,
    volume BIGINT, price_date DATE NOT NULL, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.market.market_news (
    news_id BIGINT GENERATED ALWAYS AS IDENTITY, title STRING NOT NULL,
    content STRING, source STRING, url STRING, sentiment STRING,
    published_at TIMESTAMP, created_at TIMESTAMP
);

-- =====================================================================
-- SCHEMA: analytics
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS finex_dev.analytics;

CREATE TABLE IF NOT EXISTS finex_dev.analytics.portfolio_performance (
    perf_id BIGINT GENERATED ALWAYS AS IDENTITY, portfolio_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL, total_return DOUBLE, daily_return DOUBLE,
    sharpe_ratio DOUBLE, max_drawdown DOUBLE, calculated_at TIMESTAMP, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.analytics.risk_metrics (
    metric_id BIGINT GENERATED ALWAYS AS IDENTITY, portfolio_id BIGINT NOT NULL,
    volatility DOUBLE, beta DOUBLE, var_95 DOUBLE, cvar_95 DOUBLE,
    calculated_at TIMESTAMP, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.analytics.recommendations (
    rec_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    instrument_id BIGINT, action STRING NOT NULL, reason STRING,
    confidence DOUBLE, is_active BOOLEAN, created_at TIMESTAMP
);

-- =====================================================================
-- SCHEMA: ai
-- =====================================================================
CREATE SCHEMA IF NOT EXISTS finex_dev.ai;

CREATE TABLE IF NOT EXISTS finex_dev.ai.documents (
    doc_id BIGINT GENERATED ALWAYS AS IDENTITY, title STRING NOT NULL,
    content STRING, doc_type STRING, source STRING, uploaded_by BIGINT,
    created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.ai.document_chunks (
    chunk_id BIGINT GENERATED ALWAYS AS IDENTITY, doc_id BIGINT NOT NULL,
    chunk_text STRING NOT NULL, chunk_index INT NOT NULL, token_count INT, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.ai.embeddings (
    embedding_id BIGINT GENERATED ALWAYS AS IDENTITY, chunk_id BIGINT NOT NULL,
    model_name STRING NOT NULL, embedding_vector STRING, dimensions INT, created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.ai.conversations (
    conversation_id BIGINT GENERATED ALWAYS AS IDENTITY, user_id BIGINT NOT NULL,
    title STRING, status STRING, created_at TIMESTAMP, updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS finex_dev.ai.messages (
    message_id BIGINT GENERATED ALWAYS AS IDENTITY, conversation_id BIGINT NOT NULL,
    role STRING NOT NULL, content STRING NOT NULL, citations STRING, created_at TIMESTAMP
);

-- =====================================================================
-- Verification
-- =====================================================================
SHOW SCHEMAS IN finex_dev;
SHOW TABLES IN finex_dev.core;
SHOW TABLES IN finex_dev.market;
SHOW TABLES IN finex_dev.analytics;
SHOW TABLES IN finex_dev.ai;
