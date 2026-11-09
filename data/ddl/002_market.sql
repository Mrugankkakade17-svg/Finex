-- =====================================================================
-- Task: S1-DAT-01
-- Catalog: finex_dev
-- Schema: market
-- Purpose: Market / financial instrument data
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS finex_dev.market;

-- ---------------------------------------------------------------------
-- instruments
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.market.instruments (
    instrument_id     BIGINT GENERATED ALWAYS AS IDENTITY,
    symbol            STRING NOT NULL,
    name              STRING NOT NULL,
    instrument_type   STRING NOT NULL,
    exchange          STRING,
    sector            STRING,
    is_active         BOOLEAN,
    created_at        TIMESTAMP,
    updated_at        TIMESTAMP
);

-- ---------------------------------------------------------------------
-- prices
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.market.prices (
    price_id        BIGINT GENERATED ALWAYS AS IDENTITY,
    instrument_id   BIGINT NOT NULL,
    open_price      DOUBLE,
    high_price      DOUBLE,
    low_price       DOUBLE,
    close_price     DOUBLE,
    volume          BIGINT,
    price_date      DATE NOT NULL,
    created_at      TIMESTAMP
);

-- ---------------------------------------------------------------------
-- market_news
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finex_dev.market.market_news (
    news_id         BIGINT GENERATED ALWAYS AS IDENTITY,
    title           STRING NOT NULL,
    content         STRING,
    source          STRING,
    url             STRING,
    sentiment       STRING,
    published_at    TIMESTAMP,
    created_at      TIMESTAMP
);
