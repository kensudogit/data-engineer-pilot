-- RAW layer: near-source data, loosely typed, minimal transformation.
-- Loaded directly from the source application (or from
-- backend/src/data/synth.py's synthetic dataset via
-- backend/scripts/provision_bigquery.py --load-raw).

CREATE TABLE IF NOT EXISTS `@project.raw.customers` (
  customer_id STRING,
  signup_date DATE,
  churn_date DATE,
  is_active BOOL,
  plan_type STRING,
  region STRING
);

CREATE TABLE IF NOT EXISTS `@project.raw.subscriptions` (
  subscription_id STRING,
  customer_id STRING,
  plan STRING,
  mrr NUMERIC,
  start_date DATE,
  end_date DATE,
  status STRING
);

CREATE TABLE IF NOT EXISTS `@project.raw.products` (
  product_id STRING,
  name STRING,
  category STRING,
  unit_price NUMERIC,
  launch_date DATE
);

CREATE TABLE IF NOT EXISTS `@project.raw.orders` (
  order_id STRING,
  customer_id STRING,
  order_date DATE,
  channel STRING,
  region STRING,
  order_amount NUMERIC,
  item_count INT64,
  status STRING
);

CREATE TABLE IF NOT EXISTS `@project.raw.order_items` (
  order_item_id STRING,
  order_id STRING,
  product_id STRING,
  quantity INT64,
  unit_price NUMERIC,
  discount_pct NUMERIC
);
