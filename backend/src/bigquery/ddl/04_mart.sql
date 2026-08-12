-- DATA MART layer: one feature table per ML use case (SKILL.md section 3-4).
-- Partitioned/clustered per the same rules as the DWH layer.

CREATE OR REPLACE TABLE `@project.mart.daily_sales`
PARTITION BY order_date
CLUSTER BY channel AS
SELECT order_date, channel, SUM(order_amount) AS total_amount
FROM `@project.dwh.fact_orders`
GROUP BY order_date, channel;

-- Limited to the top-20 products by revenue: ARIMA_PLUS training cost scales
-- with the number of series when time_series_id_col is used, so forecasting
-- every SKU individually would be needlessly expensive (SKILL.md section 6
-- cost checklist) for a long tail of low-volume products.
CREATE OR REPLACE TABLE `@project.mart.daily_product_demand`
PARTITION BY order_date
CLUSTER BY product_id AS
WITH top_products AS (
  SELECT product_id
  FROM `@project.dwh.fact_order_items`
  GROUP BY product_id
  ORDER BY SUM(quantity * unit_price) DESC
  LIMIT 20
)
SELECT order_date, product_id, SUM(quantity) AS quantity_sold
FROM `@project.dwh.fact_order_items`
WHERE product_id IN (SELECT product_id FROM top_products)
GROUP BY order_date, product_id;

-- Point-in-time customer features across many historical snapshots (not just
-- "as of today") so the churn model has enough labeled rows to learn from.
-- Each row's features only use orders up to its own snapshot_date, and
-- churned_next_30d only looks forward from it — no leakage.
CREATE OR REPLACE TABLE `@project.mart.customer_features`
PARTITION BY snapshot_date
CLUSTER BY customer_id AS
WITH snapshot_dates AS (
  SELECT snapshot_date
  FROM UNNEST(GENERATE_DATE_ARRAY(
    DATE_ADD((SELECT MIN(signup_date) FROM `@project.dwh.dim_customer`), INTERVAL 180 DAY),
    DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY),
    INTERVAL 30 DAY
  )) AS snapshot_date
),
base AS (
  SELECT c.customer_id, c.region, c.plan_type, c.signup_date, c.churn_date, s.snapshot_date
  FROM `@project.dwh.dim_customer` c
  CROSS JOIN snapshot_dates s
  WHERE c.signup_date <= s.snapshot_date
    AND (c.churn_date IS NULL OR c.churn_date > s.snapshot_date)
),
order_stats AS (
  SELECT
    b.customer_id,
    b.snapshot_date,
    COUNTIF(o.order_date > DATE_SUB(b.snapshot_date, INTERVAL 90 DAY) AND o.order_date <= b.snapshot_date) AS frequency_90d,
    SUM(IF(o.order_date > DATE_SUB(b.snapshot_date, INTERVAL 90 DAY) AND o.order_date <= b.snapshot_date, o.order_amount, 0)) AS monetary_90d,
    MAX(IF(o.order_date <= b.snapshot_date, o.order_date, NULL)) AS last_order_date
  FROM base b
  LEFT JOIN `@project.dwh.fact_orders` o ON o.customer_id = b.customer_id
  GROUP BY b.customer_id, b.snapshot_date
)
SELECT
  b.customer_id,
  b.snapshot_date,
  DATE_DIFF(b.snapshot_date, os.last_order_date, DAY) AS recency_days,
  IFNULL(os.frequency_90d, 0) AS frequency_90d,
  IFNULL(os.monetary_90d, 0) AS monetary_90d,
  SAFE_DIVIDE(os.monetary_90d, os.frequency_90d) AS avg_order_value,
  DATE_DIFF(b.snapshot_date, b.signup_date, DAY) AS tenure_days,
  b.plan_type,
  b.region,
  (b.churn_date IS NOT NULL
    AND b.churn_date > b.snapshot_date
    AND b.churn_date <= DATE_ADD(b.snapshot_date, INTERVAL 30 DAY)) AS churned_next_30d
FROM base b
JOIN order_stats os ON os.customer_id = b.customer_id AND os.snapshot_date = b.snapshot_date;

CREATE OR REPLACE TABLE `@project.mart.order_transaction_features`
PARTITION BY order_date
CLUSTER BY customer_id AS
WITH item_agg AS (
  SELECT order_id, AVG(unit_price) AS avg_unit_price, AVG(discount_pct) AS discount_pct
  FROM `@project.dwh.fact_order_items`
  GROUP BY order_id
)
SELECT
  o.order_id,
  o.order_date,
  o.customer_id,
  o.order_amount,
  o.item_count,
  ia.discount_pct,
  ia.avg_unit_price,
  TIMESTAMP_DIFF(
    TIMESTAMP(o.order_date),
    TIMESTAMP(LAG(o.order_date) OVER (PARTITION BY o.customer_id ORDER BY o.order_date)),
    HOUR
  ) AS hours_since_last_order
FROM `@project.dwh.fact_orders` o
JOIN item_agg ia USING (order_id);
