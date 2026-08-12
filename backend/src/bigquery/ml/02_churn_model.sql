-- 解約予測 (Churn Prediction) — LOGISTIC_REG on point-in-time customer features.
-- Demo-mode equivalent: scikit-learn LogisticRegression in
-- backend/src/services/churn_service.py, evaluated with holdout AUC.

CREATE OR REPLACE MODEL `@project.mart.churn_model`
OPTIONS (
  model_type = 'LOGISTIC_REG',
  input_label_cols = ['churned_next_30d'],
  auto_class_weights = TRUE,
  data_split_method = 'AUTO_SPLIT'
) AS
SELECT
  recency_days,
  frequency_90d,
  monetary_90d,
  avg_order_value,
  tenure_days,
  plan_type,
  region,
  churned_next_30d
FROM `@project.mart.customer_features`;

-- Serving query (score all customers as of the latest snapshot):
-- SELECT
--   customer_id,
--   predicted_churned_next_30d,
--   predicted_churned_next_30d_probs
-- FROM ML.PREDICT(
--   MODEL `@project.mart.churn_model`,
--   (SELECT * FROM `@project.mart.customer_features`
--    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `@project.mart.customer_features`))
-- );
