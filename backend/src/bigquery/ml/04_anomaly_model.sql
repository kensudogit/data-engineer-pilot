-- 異常検知 (Anomaly Detection) — AUTOENCODER + ML.DETECT_ANOMALIES.
--
-- Chosen over a KMEANS-distance heuristic or an ARIMA_PLUS-residual approach
-- because the target here is transaction-level, non-sequential tabular
-- anomaly detection (fraud-like/outlier orders), which is exactly
-- AUTOENCODER's documented BigQuery ML use case: it learns to reconstruct
-- "normal" orders and ML.DETECT_ANOMALIES flags rows whose reconstruction
-- error exceeds a contamination-based threshold.
--
-- Demo-mode equivalent: scikit-learn IsolationForest(contamination=0.015) in
-- backend/src/services/anomaly_service.py.

CREATE OR REPLACE MODEL `@project.mart.order_anomaly_model`
OPTIONS (
  model_type = 'AUTOENCODER',
  activation_fn = 'RELU',
  hidden_units = [16, 8, 4, 8, 16],
  dropout = 0.2,
  learn_rate = 0.001,
  max_iterations = 20
) AS
SELECT
  order_amount,
  item_count,
  discount_pct,
  avg_unit_price,
  hours_since_last_order
FROM `@project.mart.order_transaction_features`;

-- Serving query (flag anomalies in the last 30 days):
-- SELECT order_id, is_anomaly, normalized_reconstruction_error
-- FROM ML.DETECT_ANOMALIES(
--   MODEL `@project.mart.order_anomaly_model`,
--   STRUCT(0.015 AS contamination),
--   (SELECT * FROM `@project.mart.order_transaction_features`
--    WHERE order_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY))
-- );
