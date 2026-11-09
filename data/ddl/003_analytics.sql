-- =====================================================================
-- Task: S1-DAT-01
-- Catalog: finex_dev
-- Schema: analytics
-- Purpose: Computed / aggregated analytical data
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS finex_dev.analytics;

-- ---------------------------------------------------------------------
-- portfolio_performance
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.analytics.portfolio_performance (
    perf_id         BIGINT GENERATED ALWAYS AS IDENTITY,
    portfolio_id    BIGINT NOT NULL,
    user_id         BIGINT NOT NULL,
    total_return    DOUBLE,
    daily_return    DOUBLE,
    sharpe_ratio    DOUBLE,
    max_drawdown    DOUBLE,
    calculated_at   TIMESTAMP,
    created_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- risk_metrics
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.analytics.risk_metrics (
    metric_id       BIGINT GENERATED ALWAYS AS IDENTITY,
    portfolio_id    BIGINT NOT NULL,
    volatility      DOUBLE,
    beta            DOUBLE,
    var_95          DOUBLE,
    cvar_95         DOUBLE,
    calculated_at   TIMESTAMP,
    created_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- recommendations
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.analytics.recommendations (
    rec_id          BIGINT GENERATED ALWAYS AS IDENTITY,
    user_id         BIGINT NOT NULL,
    instrument_id   BIGINT,
    action          STRING NOT NULL,
    reason          STRING,
    confidence      DOUBLE,
    is_active       BOOLEAN,
    created_at      TIMESTAMP
);
