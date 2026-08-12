-- 解約予測 (Churn Prediction) — SNOWFLAKE.ML.CLASSIFICATION on point-in-time
-- customer features. Cortex ML Functions equivalent of
-- backend/src/bigquery/ml/02_churn_model.sql's LOGISTIC_REG. Demo-mode
-- equivalent: scikit-learn LogisticRegression in
-- backend/src/services/churn_service.py, evaluated with holdout AUC.
--
-- Run once via backend/scripts/provision_snowflake.py --create-models.
-- Requires the executing role to have the SNOWFLAKE.CORTEX_USER database
-- role, plus CREATE SNOWFLAKE.ML.CLASSIFICATION privilege on this schema.

CREATE OR REPLACE VIEW @database.mart.customer_features_view AS
SELECT
  recency_days,
  frequency_90d,
  monetary_90d,
  avg_order_value,
  tenure_days,
  plan_type,
  region,
  churned_next_30d
FROM @database.mart.customer_features
WHERE snapshot_date < DATEADD('day', -30, CURRENT_DATE());
-- excludes snapshots too recent to have a resolved churned_next_30d label

CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION churn_model(
  INPUT_DATA => SYSTEM$REFERENCE('VIEW', '@database.mart.customer_features_view'),
  TARGET_COLNAME => 'churned_next_30d'
);

-- Serving query (score customers as of the latest snapshot):
-- SELECT
--   customer_id,
--   churn_model!PREDICT(OBJECT_CONSTRUCT(*)) AS prediction
-- FROM @database.mart.customer_features
-- WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM @database.mart.customer_features);
--
-- Evaluation metrics (used for the ai_insight prompt's AUC figure):
-- CALL churn_model!SHOW_EVALUATION_METRICS();
