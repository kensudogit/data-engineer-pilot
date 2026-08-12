-- RAW layer: near-source data, loosely typed, minimal transformation.
-- Same shape as backend/src/bigquery/ddl/01_raw.sql — loaded directly from
-- the synthetic dataset via backend/scripts/provision_snowflake.py
-- --load-raw. Type mapping vs. BigQuery: STRING, NUMERIC, INT64, BOOL are
-- all valid Snowflake aliases too, but VARCHAR/NUMBER/INTEGER/BOOLEAN are
-- used here as the idiomatic Snowflake spelling.

CREATE TABLE IF NOT EXISTS @database.raw.customers (
  customer_id VARCHAR,
  signup_date DATE,
  churn_date DATE,
  is_active BOOLEAN,
  plan_type VARCHAR,
  region VARCHAR
);

CREATE TABLE IF NOT EXISTS @database.raw.subscriptions (
  subscription_id VARCHAR,
  customer_id VARCHAR,
  plan VARCHAR,
  mrr NUMBER(12, 2),
  start_date DATE,
  end_date DATE,
  status VARCHAR
);

CREATE TABLE IF NOT EXISTS @database.raw.products (
  product_id VARCHAR,
  name VARCHAR,
  category VARCHAR,
  unit_price NUMBER(12, 2),
  launch_date DATE
);

CREATE TABLE IF NOT EXISTS @database.raw.orders (
  order_id VARCHAR,
  customer_id VARCHAR,
  order_date DATE,
  channel VARCHAR,
  region VARCHAR,
  order_amount NUMBER(12, 2),
  item_count INTEGER,
  status VARCHAR
);

CREATE TABLE IF NOT EXISTS @database.raw.order_items (
  order_item_id VARCHAR,
  order_id VARCHAR,
  product_id VARCHAR,
  quantity INTEGER,
  unit_price NUMBER(12, 2),
  discount_pct NUMBER(5, 4)
);
