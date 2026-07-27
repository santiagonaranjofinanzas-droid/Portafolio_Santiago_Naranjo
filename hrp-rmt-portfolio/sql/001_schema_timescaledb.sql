CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS market_prices (
    ts timestamptz NOT NULL,
    ticker text NOT NULL,
    open double precision,
    high double precision,
    low double precision,
    close double precision,
    adj_open double precision,
    adj_high double precision,
    adj_low double precision,
    adj_close double precision,
    adj_volume double precision,
    volume double precision,
    div_cash double precision,
    split_factor double precision,
    source text NOT NULL DEFAULT 'tiingo',
    fetch_timestamp timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ts, ticker)
);
SELECT create_hypertable('market_prices', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS target_weights (
    ts timestamptz NOT NULL,
    model_version text NOT NULL,
    ticker text NOT NULL,
    target_weight_raw double precision,
    target_weight_capped double precision,
    vol_scalar double precision,
    final_target_weight double precision,
    sigma_forecast double precision,
    quality_status text,
    rebalance_eligible text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ts, model_version, ticker)
);
SELECT create_hypertable('target_weights', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS rebalance_decisions (
    ts timestamptz NOT NULL,
    decision text NOT NULL,
    turnover double precision,
    is_month_end boolean,
    message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ts, decision)
);
SELECT create_hypertable('rebalance_decisions', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS orders (
    ts timestamptz NOT NULL,
    ticker text NOT NULL,
    side text,
    target_weight double precision,
    current_weight double precision,
    delta_weight double precision,
    portfolio_value double precision,
    trade_value double precision,
    estimated_commission double precision,
    estimated_slippage double precision,
    estimated_spread_cost double precision,
    estimated_total_cost double precision,
    order_status text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ts, ticker, order_status)
);
SELECT create_hypertable('orders', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS fills (
    ts timestamptz NOT NULL,
    ticker text NOT NULL,
    side text,
    weight_delta double precision,
    fill_status text,
    estimated_total_cost double precision,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ts, ticker, fill_status)
);
SELECT create_hypertable('fills', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS positions (
    ts timestamptz NOT NULL,
    ticker text NOT NULL,
    weight double precision,
    source text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (ts, ticker)
);
SELECT create_hypertable('positions', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS portfolio_nav (
    ts timestamptz NOT NULL PRIMARY KEY,
    portfolio_value double precision,
    daily_pnl double precision,
    drawdown double precision,
    created_at timestamptz NOT NULL DEFAULT now()
);
SELECT create_hypertable('portfolio_nav', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS tracking_error (
    ts timestamptz NOT NULL PRIMARY KEY,
    weight_l1_tracking_error double precision,
    created_at timestamptz NOT NULL DEFAULT now()
);
SELECT create_hypertable('tracking_error', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS costs (
    ts timestamptz NOT NULL PRIMARY KEY,
    estimated_total_cost double precision,
    fills integer,
    created_at timestamptz NOT NULL DEFAULT now()
);
SELECT create_hypertable('costs', 'ts', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS data_quality_log (
    event_time timestamptz NOT NULL,
    asof_date date,
    ticker text,
    status text,
    message text,
    created_at timestamptz NOT NULL DEFAULT now()
);
SELECT create_hypertable('data_quality_log', 'event_time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS pipeline_status (
    event_time timestamptz NOT NULL,
    asof_date date,
    stage text,
    status text,
    message text,
    created_at timestamptz NOT NULL DEFAULT now()
);
SELECT create_hypertable('pipeline_status', 'event_time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS risk_log (
    event_time timestamptz NOT NULL,
    asof_date date,
    status text,
    max_weight double precision,
    tracking_error double precision,
    alerts text,
    created_at timestamptz NOT NULL DEFAULT now()
);
SELECT create_hypertable('risk_log', 'event_time', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS file_hashes (
    event_time timestamptz NOT NULL,
    source text,
    path text,
    sha256 text,
    size_bytes bigint,
    created_at timestamptz NOT NULL DEFAULT now()
);
SELECT create_hypertable('file_hashes', 'event_time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_market_prices_ticker_ts ON market_prices (ticker, ts DESC);
CREATE INDEX IF NOT EXISTS idx_target_weights_ticker_ts ON target_weights (ticker, ts DESC);
CREATE INDEX IF NOT EXISTS idx_positions_ticker_ts ON positions (ticker, ts DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status_ts ON orders (order_status, ts DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_data_quality_log_event ON data_quality_log (event_time, asof_date, ticker, status, message);
CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_status_event ON pipeline_status (event_time, asof_date, stage, status, message);
CREATE UNIQUE INDEX IF NOT EXISTS uq_risk_log_event ON risk_log (event_time, asof_date, status, alerts);
CREATE UNIQUE INDEX IF NOT EXISTS uq_file_hashes_event ON file_hashes (event_time, path, sha256);
