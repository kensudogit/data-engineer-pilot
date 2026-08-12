-- DATA MART layer: one feature table per ML use case (SKILL.md section
-- 3-4). Same logical shapes as backend/src/bigquery/ddl/04_mart.sql,
-- translated to Snowflake SQL. See the dialect notes inline at each
-- non-trivial translation — this file is the highest-risk translation in
-- the Snowflake DDL set (point-in-time snapshot generation + several
-- function renames), reviewed function-by-function against BigQuery's
-- original, not machine-translated.
--
-- CLUSTER BY intentionally omitted throughout — see the note in 03_dwh.sql.

CREATE OR REPLACE TABLE @database.mart.daily_sales AS
SELECT order_date, channel, SUM(order_amount) AS total_amount
FROM @database.dwh.fact_orders
GROUP BY order_date, channel;

-- Limited to the top-20 products by revenue: forecasting cost scales with
-- the number of series when a time-series-id column is used
-- (SNOWFLAKE.ML.FORECAST's SERIES_COLNAME, like BigQuery ARIMA_PLUS's
-- time_series_id_col), so forecasting every SKU individually would be
-- needlessly expensive (SKILL.md section 6 cost checklist) for a long tail
-- of low-volume products.
CREATE OR REPLACE TABLE @database.mart.daily_product_demand AS
WITH top_products AS (
  SELECT product_id
  FROM @database.dwh.fact_order_items
  GROUP BY product_id
  ORDER BY SUM(quantity * unit_price) DESC
  LIMIT 20
)
SELECT order_date, product_id, SUM(quantity) AS quantity_sold
FROM @database.dwh.fact_order_items
WHERE product_id IN (SELECT product_id FROM top_products)
GROUP BY order_date, product_id;

-- Point-in-time customer features across many historical snapshots (not
-- just "as of today") so the churn model has enough labeled rows to learn
-- from. Each row's features only use orders up to its own snapshot_date,
-- and churned_next_30d only looks forward from it — no leakage. Identical
-- logic to the BigQuery version; only the snapshot-date generation and a
-- handful of function names differ (see comments below).
CREATE OR REPLACE TABLE @database.mart.customer_features AS
WITH snapshot_dates AS (
  -- Snowflake has no GENERATE_DATE_ARRAY/UNNEST equivalent. Standard idiom:
  -- GENERATOR(ROWCOUNT=>N) + SEQ4() to produce N rows, DATEADD to project
  -- each row to a 30-day-spaced date starting 180 days after the earliest
  -- signup, then filter down to dates at least 30 days before today.
  -- ROWCOUNT=>100 (=> up to ~8 years of 30-day steps) comfortably covers
  -- this pilot's ~2-year synthetic dataset.
  SELECT snapshot_date
  FROM (
    SELECT
      DATEADD(
        'day',
        SEQ4() * 30,
        DATEADD('day', 180, (SELECT MIN(signup_date) FROM @database.dwh.dim_customer))
      ) AS snapshot_date
    FROM TABLE(GENERATOR(ROWCOUNT => 100))
  )
  WHERE snapshot_date <= DATEADD('day', -30, CURRENT_DATE())
),
base AS (
  SELECT c.customer_id, c.region, c.plan_type, c.signup_date, c.churn_date, s.snapshot_date
  FROM @database.dwh.dim_customer c
  CROSS JOIN snapshot_dates s
  WHERE c.signup_date <= s.snapshot_date
    AND (c.churn_date IS NULL OR c.churn_date > s.snapshot_date)
),
order_stats AS (
  SELECT
    b.customer_id,
    b.snapshot_date,
    -- COUNTIF -> COUNT_IF, IF(...) -> IFF(...): same 3-arg shape, renamed.
    COUNT_IF(o.order_date > DATEADD('day', -90, b.snapshot_date) AND o.order_date <= b.snapshot_date) AS frequency_90d,
    SUM(IFF(o.order_date > DATEADD('day', -90, b.snapshot_date) AND o.order_date <= b.snapshot_date, o.order_amount, 0)) AS monetary_90d,
    MAX(IFF(o.order_date <= b.snapshot_date, o.order_date, NULL)) AS last_order_date
  FROM base b
  LEFT JOIN @database.dwh.fact_orders o ON o.customer_id = b.customer_id
  GROUP BY b.customer_id, b.snapshot_date
)
SELECT
  b.customer_id,
  b.snapshot_date,
  -- DATE_DIFF(a,b,part) = a-b in BigQuery; DATEDIFF(part,start,end) = end-start
  -- in Snowflake. To get the same "snapshot_date minus last_order_date", the
  -- two date arguments swap position, not just the function name.
  DATEDIFF('day', os.last_order_date, b.snapshot_date) AS recency_days,
  IFNULL(os.frequency_90d, 0) AS frequency_90d,
  IFNULL(os.monetary_90d, 0) AS monetary_90d,
  -- SAFE_DIVIDE -> DIV0NULL (not DIV0, which returns 0 instead of NULL on a
  -- zero denominator — the wrong semantic here).
  DIV0NULL(os.monetary_90d, os.frequency_90d) AS avg_order_value,
  DATEDIFF('day', b.signup_date, b.snapshot_date) AS tenure_days,
  b.plan_type,
  b.region,
  (b.churn_date IS NOT NULL
    AND b.churn_date > b.snapshot_date
    AND b.churn_date <= DATEADD('day', 30, b.snapshot_date)) AS churned_next_30d
FROM base b
JOIN order_stats os ON os.customer_id = b.customer_id AND os.snapshot_date = b.snapshot_date;

CREATE OR REPLACE TABLE @database.mart.order_transaction_features AS
WITH item_agg AS (
  SELECT order_id, AVG(unit_price) AS avg_unit_price, AVG(discount_pct) AS discount_pct
  FROM @database.dwh.fact_order_items
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
  -- TIMESTAMP_DIFF(TIMESTAMP(a),TIMESTAMP(b),HOUR) -> DATEDIFF('hour',b,a).
  -- Snowflake's DATEDIFF accepts DATE operands directly (no TIMESTAMP()
  -- cast needed) and, like BigQuery's TIMESTAMP(date) cast to midnight,
  -- computes the diff from each date's midnight — same semantics.
  DATEDIFF(
    'hour',
    LAG(o.order_date) OVER (PARTITION BY o.customer_id ORDER BY o.order_date),
    o.order_date
  ) AS hours_since_last_order
FROM @database.dwh.fact_orders o
JOIN item_agg ia USING (order_id);
