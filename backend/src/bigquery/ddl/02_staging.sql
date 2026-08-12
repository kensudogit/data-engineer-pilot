-- STAGING layer: type coercion, dedup, and basic validation on top of RAW
-- (SKILL.md section 3: "データ型変換、NULL処理、重複排除、コード変換").
-- Materialized as CREATE OR REPLACE TABLE ... AS SELECT (ELT), run after
-- 01_raw.sql has been loaded.

CREATE OR REPLACE TABLE `@project.staging.customers` AS
SELECT DISTINCT
  customer_id,
  signup_date,
  churn_date,
  COALESCE(is_active, churn_date IS NULL) AS is_active,
  IFNULL(plan_type, 'unknown') AS plan_type,
  IFNULL(region, 'unknown') AS region
FROM `@project.raw.customers`
WHERE customer_id IS NOT NULL;

CREATE OR REPLACE TABLE `@project.staging.subscriptions` AS
SELECT DISTINCT
  subscription_id,
  customer_id,
  plan,
  mrr,
  start_date,
  end_date,
  status
FROM `@project.raw.subscriptions`
WHERE subscription_id IS NOT NULL
  AND customer_id IS NOT NULL;

CREATE OR REPLACE TABLE `@project.staging.products` AS
SELECT DISTINCT
  product_id,
  name,
  category,
  unit_price,
  launch_date
FROM `@project.raw.products`
WHERE product_id IS NOT NULL
  AND unit_price > 0;

CREATE OR REPLACE TABLE `@project.staging.orders` AS
SELECT DISTINCT
  order_id,
  customer_id,
  order_date,
  channel,
  region,
  order_amount,
  item_count,
  status
FROM `@project.raw.orders`
WHERE order_id IS NOT NULL
  AND customer_id IS NOT NULL
  AND order_amount >= 0;

CREATE OR REPLACE TABLE `@project.staging.order_items` AS
SELECT DISTINCT
  order_item_id,
  order_id,
  product_id,
  quantity,
  unit_price,
  discount_pct
FROM `@project.raw.order_items`
WHERE order_item_id IS NOT NULL
  AND order_id IS NOT NULL
  AND quantity > 0;
