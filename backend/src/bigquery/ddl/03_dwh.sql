-- DWH layer: dimensional model for cross-domain analysis (SKILL.md section 3).
-- Fact tables are partitioned by date and clustered by the columns they're
-- most commonly filtered/joined on (SKILL.md section 4).

CREATE OR REPLACE TABLE `@project.dwh.dim_customer` AS
SELECT
  customer_id,
  region,
  plan_type,
  signup_date,
  churn_date,
  is_active
FROM `@project.staging.customers`;

CREATE OR REPLACE TABLE `@project.dwh.dim_product` AS
SELECT
  product_id,
  category,
  unit_price,
  launch_date
FROM `@project.staging.products`;

-- Simple calendar dimension, generated once for the dataset's date range.
CREATE OR REPLACE TABLE `@project.dwh.dim_date` AS
SELECT
  d AS date,
  EXTRACT(YEAR FROM d) AS year,
  EXTRACT(MONTH FROM d) AS month,
  EXTRACT(DAYOFWEEK FROM d) AS day_of_week,
  EXTRACT(DAYOFWEEK FROM d) IN (1, 7) AS is_weekend,
  -- Placeholder JP-holiday flag; a real deployment should join a maintained
  -- holiday calendar table instead of hardcoding this.
  FALSE AS is_holiday_jp
FROM UNNEST(GENERATE_DATE_ARRAY('2023-01-01', CURRENT_DATE())) AS d;

CREATE TABLE IF NOT EXISTS `@project.dwh.fact_orders`
PARTITION BY order_date
CLUSTER BY customer_id AS
SELECT
  order_id,
  customer_id,
  order_date,
  channel,
  region,
  order_amount,
  item_count,
  status
FROM `@project.staging.orders`;

CREATE TABLE IF NOT EXISTS `@project.dwh.fact_order_items`
PARTITION BY order_date
CLUSTER BY product_id, customer_id AS
SELECT
  oi.order_item_id,
  oi.order_id,
  o.order_date,
  oi.product_id,
  o.customer_id,
  oi.quantity,
  oi.unit_price,
  oi.discount_pct
FROM `@project.staging.order_items` oi
JOIN `@project.staging.orders` o USING (order_id);

CREATE TABLE IF NOT EXISTS `@project.dwh.fact_subscription_events`
PARTITION BY event_date
CLUSTER BY customer_id AS
SELECT
  subscription_id,
  customer_id,
  start_date AS event_date,
  'started' AS event_type,
  plan,
  mrr
FROM `@project.staging.subscriptions`
UNION ALL
SELECT
  subscription_id,
  customer_id,
  end_date AS event_date,
  'cancelled' AS event_type,
  plan,
  mrr
FROM `@project.staging.subscriptions`
WHERE end_date IS NOT NULL;
