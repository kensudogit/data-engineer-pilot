-- 売上予測 (Sales Forecasting) — ARIMA_PLUS, one series per channel.
-- Demo-mode equivalent: statsmodels ExponentialSmoothing (Holt-Winters),
-- fit per channel in backend/src/services/sales_forecast_service.py.

CREATE OR REPLACE MODEL `@project.mart.sales_forecast_model`
OPTIONS (
  model_type = 'ARIMA_PLUS',
  time_series_timestamp_col = 'order_date',
  time_series_data_col = 'total_amount',
  time_series_id_col = 'channel',
  auto_arima = TRUE,
  data_frequency = 'DAILY',
  holiday_region = 'JP'
) AS
SELECT order_date, channel, total_amount
FROM `@project.mart.daily_sales`;

-- Serving query (30-day horizon, 80% confidence interval):
-- SELECT *
-- FROM ML.FORECAST(
--   MODEL `@project.mart.sales_forecast_model`,
--   STRUCT(30 AS horizon, 0.8 AS confidence_level)
-- );
