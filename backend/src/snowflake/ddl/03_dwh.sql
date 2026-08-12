-- DWH layer: dimensional model for cross-domain analysis (SKILL.md section
-- 3). Same shape as backend/src/bigquery/ddl/03_dwh.sql.
--
-- Deliberate divergence from the BigQuery DDL: BigQuery's fact tables use
-- `PARTITION BY <date>` because BigQuery bills by bytes scanned, so
-- partition pruning is a direct cost control even at small scale. Snowflake
-- has no equivalent explicit partitioning — storage is automatically
-- divided into micro-partitions — and it bills by warehouse-second, not
-- bytes scanned, so `CLUSTER BY` (Snowflake's only physical-layout clause)
-- is recommended by Snowflake's own docs only for multi-TB tables where the
-- clustering-maintenance cost is worth it. This pilot's synthetic tables
-- are tiny, so CLUSTER BY is intentionally omitted below rather than
-- copied over as cargo-culted BigQuery habit.

CREATE OR REPLACE TABLE @database.dwh.dim_customer AS
SELECT
  customer_id,
  region,
  plan_type,
  signup_date,
  churn_date,
  is_active
FROM @database.staging.customers;

CREATE OR REPLACE TABLE @database.dwh.dim_product AS
SELECT
  product_id,
  category,
  unit_price,
  launch_date
FROM @database.staging.products;

-- Simple calendar dimension. Snowflake has no GENERATE_DATE_ARRAY /
-- UNNEST equivalent — the standard idiom is GENERATOR(ROWCOUNT=>N) + SEQ4()
-- to produce N rows, DATEADD to project each row to a date, and QUALIFY to
-- cap the range (3653 rows = 10 years, comfortably covers 2023-01-01 to
-- today for this pilot's ~2-year synthetic dataset).
--
-- DAYOFWEEK also differs from BigQuery: Snowflake's DAYOFWEEK() returns
-- 0=Sunday..6=Saturday (not BigQuery's 1=Sunday..7=Saturday), so the
-- weekend check below uses (0, 6), not BigQuery's (1, 7).
CREATE OR REPLACE TABLE @database.dwh.dim_date AS
SELECT
  d AS date,
  YEAR(d) AS year,
  MONTH(d) AS month,
  DAYOFWEEK(d) AS day_of_week,
  DAYOFWEEK(d) IN (0, 6) AS is_weekend,
  -- Placeholder JP-holiday flag; a real deployment should join a maintained
  -- holiday calendar table instead of hardcoding this.
  FALSE AS is_holiday_jp
FROM (
  SELECT DATEADD('day', SEQ4(), DATE '2023-01-01') AS d
  FROM TABLE(GENERATOR(ROWCOUNT => 3653))
)
WHERE d <= CURRENT_DATE();

CREATE OR REPLACE TABLE @database.dwh.fact_orders AS
SELECT
  order_id,
  customer_id,
  order_date,
  channel,
  region,
  order_amount,
  item_count,
  status
FROM @database.staging.orders;
-- CLUSTER BY (order_date, customer_id) -- see note above; omitted for this pilot's table size

CREATE OR REPLACE TABLE @database.dwh.fact_order_items AS
SELECT
  oi.order_item_id,
  oi.order_id,
  o.order_date,
  oi.product_id,
  o.customer_id,
  oi.quantity,
  oi.unit_price,
  oi.discount_pct
FROM @database.staging.order_items oi
JOIN @database.staging.orders o USING (order_id);
-- CLUSTER BY (order_date, product_id, customer_id) -- see note above; omitted for this pilot's table size

CREATE OR REPLACE TABLE @database.dwh.fact_subscription_events AS
SELECT
  subscription_id,
  customer_id,
  start_date AS event_date,
  'started' AS event_type,
  plan,
  mrr
FROM @database.staging.subscriptions
UNION ALL
SELECT
  subscription_id,
  customer_id,
  end_date AS event_date,
  'cancelled' AS event_type,
  plan,
  mrr
FROM @database.staging.subscriptions
WHERE end_date IS NOT NULL;
