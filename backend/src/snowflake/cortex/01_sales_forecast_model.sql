-- 売上予測 (Sales Forecasting) — SNOWFLAKE.ML.FORECAST, one series per channel.
-- Cortex ML Functions equivalent of backend/src/bigquery/ml/01_sales_forecast_model.sql's
-- ARIMA_PLUS. Demo-mode equivalent: statsmodels ExponentialSmoothing
-- (Holt-Winters), fit per channel in
-- backend/src/services/sales_forecast_service.py.
--
-- Run once via backend/scripts/provision_snowflake.py --create-models —
-- this is a schema-level object creation, not something re-run per
-- request (see src/snowflake/README notes / plan doc). SYSTEM$REFERENCE
-- takes a change-tracking snapshot of the named view/table at creation
-- time; re-run this CREATE OR REPLACE after mart.daily_sales meaningfully
-- changes.

CREATE OR REPLACE VIEW @database.mart.daily_sales_view AS
SELECT order_date, channel, total_amount FROM @database.mart.daily_sales;

CREATE OR REPLACE SNOWFLAKE.ML.FORECAST sales_forecast_model(
  INPUT_DATA => SYSTEM$REFERENCE('VIEW', '@database.mart.daily_sales_view'),
  TIMESTAMP_COLNAME => 'order_date',
  TARGET_COLNAME => 'total_amount',
  SERIES_COLNAME => 'channel'
);

-- Serving query (30-day horizon, 80% prediction interval — matching the
-- BigQuery ARIMA_PLUS serving query's confidence_level=0.8 convention):
-- CALL sales_forecast_model!FORECAST(
--   FORECASTING_PERIODS => 30,
--   CONFIG_OBJECT => {'prediction_interval': 0.8}
-- );
-- SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
