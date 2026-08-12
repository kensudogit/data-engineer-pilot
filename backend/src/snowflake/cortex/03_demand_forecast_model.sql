-- 需要予測 (Demand Forecasting) — SNOWFLAKE.ML.FORECAST, one series per
-- product. Cortex ML Functions equivalent of
-- backend/src/bigquery/ml/05_demand_forecast_model.sql's ARIMA_PLUS.
-- Limited to the top-20 products by revenue already at the
-- mart.daily_product_demand level (see ddl/04_mart.sql) — training one
-- FORECAST series per SKU for the full catalog would scale training cost
-- with the long tail of low-volume products for little forecasting value
-- (SKILL.md section 6). Demo-mode equivalent: statsmodels
-- ExponentialSmoothing fit per product in
-- backend/src/services/demand_forecast_service.py.

CREATE OR REPLACE VIEW @database.mart.daily_product_demand_view AS
SELECT order_date, product_id, quantity_sold FROM @database.mart.daily_product_demand;

CREATE OR REPLACE SNOWFLAKE.ML.FORECAST demand_forecast_model(
  INPUT_DATA => SYSTEM$REFERENCE('VIEW', '@database.mart.daily_product_demand_view'),
  TIMESTAMP_COLNAME => 'order_date',
  TARGET_COLNAME => 'quantity_sold',
  SERIES_COLNAME => 'product_id'
);

-- Serving query (30-day horizon, 80% prediction interval):
-- CALL demand_forecast_model!FORECAST(
--   FORECASTING_PERIODS => 30,
--   CONFIG_OBJECT => {'prediction_interval': 0.8}
-- );
-- SELECT * FROM TABLE(RESULT_SCAN(LAST_QUERY_ID()));
