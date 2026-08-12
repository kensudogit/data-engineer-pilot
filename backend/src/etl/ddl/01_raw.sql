-- RAW tables for the PostgreSQL "operational source system" — same 5
-- tables, same logical shape as backend/src/snowflake/ddl/01_raw.sql (the
-- eventual Snowflake RAW layer this data is pipelined into via
-- Python ETL -> S3 -> Snowpipe), with FK constraints and indexes added
-- since this is a real, functioning Postgres database, not just DDL text.
--
-- Loaded with backend/src/etl/postgres_source.py --seed (the same
-- generate_dataset(seed=42) synthetic dataset used everywhere else in
-- this project, minus the two generator-internal-only columns
-- (customers.archetype, orders.is_injected_anomaly) that don't belong in
-- any table meant to represent a real operational system).

CREATE TABLE IF NOT EXISTS raw.customers (
  customer_id   VARCHAR PRIMARY KEY,
  signup_date   DATE NOT NULL,
  churn_date    DATE,
  is_active     BOOLEAN NOT NULL,
  plan_type     VARCHAR NOT NULL,
  region        VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.subscriptions (
  subscription_id VARCHAR PRIMARY KEY,
  customer_id     VARCHAR NOT NULL REFERENCES raw.customers(customer_id),
  plan            VARCHAR NOT NULL,
  mrr             NUMERIC(12, 2) NOT NULL,
  start_date      DATE NOT NULL,
  end_date        DATE,
  status          VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.products (
  product_id   VARCHAR PRIMARY KEY,
  name         VARCHAR NOT NULL,
  category     VARCHAR NOT NULL,
  unit_price   NUMERIC(12, 2) NOT NULL,
  launch_date  DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.orders (
  order_id      VARCHAR PRIMARY KEY,
  customer_id   VARCHAR NOT NULL REFERENCES raw.customers(customer_id),
  order_date    DATE NOT NULL,
  channel       VARCHAR NOT NULL,
  region        VARCHAR NOT NULL,
  order_amount  NUMERIC(12, 2) NOT NULL,
  item_count    INTEGER NOT NULL,
  status        VARCHAR NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON raw.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_order_date ON raw.orders(order_date);

CREATE TABLE IF NOT EXISTS raw.order_items (
  order_item_id  VARCHAR PRIMARY KEY,
  order_id       VARCHAR NOT NULL REFERENCES raw.orders(order_id),
  product_id     VARCHAR NOT NULL REFERENCES raw.products(product_id),
  quantity       INTEGER NOT NULL,
  unit_price     NUMERIC(12, 2) NOT NULL,
  discount_pct   NUMERIC(5, 4) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON raw.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON raw.order_items(product_id);
