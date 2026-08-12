-- 需要予測 (Demand Forecasting) — ARIMA_PLUS, one series per product.
-- Limited to the top-20 products by revenue at the mart.daily_product_demand
-- level already (see ddl/04_mart.sql) — training one ARIMA_PLUS series per
-- SKU for the full catalog would scale training cost with the long tail of
-- low-volume products for little forecasting value (SKILL.md section 6).
-- Demo-mode equivalent: statsmodels ExponentialSmoothing fit per product in
-- backend/src/services/demand_forecast_service.py.

CREATE OR REPLACE MODEL `@project.mart.demand_forecast_model`
OPTIONS (
  model_type = 'ARIMA_PLUS',
  time_series_timestamp_col = 'order_date',
  time_series_data_col = 'quantity_sold',
  time_series_id_col = 'product_id',
  auto_arima = TRUE,
  data_frequency = 'DAILY',
  holiday_region = 'JP'
) AS
SELECT order_date, product_id, quantity_sold
FROM `@project.mart.daily_product_demand`;

-- Serving query (14-day horizon, 80% confidence interval):
-- SELECT *
-- FROM ML.FORECAST(
--   MODEL `@project.mart.demand_forecast_model`,
--   STRUCT(14 AS horizon, 0.8 AS confidence_level)
-- );
