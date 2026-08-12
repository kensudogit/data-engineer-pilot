from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.data import features
from src.data.synth import SyntheticDataset
from src.schemas.common import TimeSeriesPoint
from src.schemas.sales_forecast import SalesForecastResponse

MODEL_NAME = "sales_forecast_model"
DEFAULT_HORIZON_DAYS = 30
SEASONAL_PERIOD = 7  # weekly seasonality
HOLDOUT_DAYS = 14
Z80 = 1.2816  # z-score for an 80% interval, matching the BigQuery ML confidence_level=0.8 convention used elsewhere


@dataclass
class ChannelSeries:
    history: pd.Series
    fitted: object  # statsmodels HoltWintersResultsWrapper, refit on the full series


@dataclass
class SalesForecastState:
    channels: dict[str, ChannelSeries]
    metrics: dict[str, dict[str, float]]


def _fit_series(series: pd.Series):
    return ExponentialSmoothing(
        series, trend="add", seasonal="add", seasonal_periods=SEASONAL_PERIOD, initialization_method="estimated"
    ).fit()


def prepare(dataset: SyntheticDataset) -> SalesForecastState:
    """Trains one Holt-Winters model per channel once, at startup — services
    never refit per-request (see the plan's dataset-consistency note)."""
    daily = features.daily_sales(dataset)
    channels: dict[str, ChannelSeries] = {}
    metrics: dict[str, dict[str, float]] = {}

    for channel in sorted(daily["channel"].unique()):
        sub = daily[daily["channel"] == channel].sort_values("order_date")
        series = pd.Series(
            sub["total_amount"].to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(sub["order_date"]))
        ).asfreq("D", fill_value=0.0)

        train, test = series.iloc[:-HOLDOUT_DAYS], series.iloc[-HOLDOUT_DAYS:]
        holdout_model = _fit_series(train)
        pred = holdout_model.forecast(HOLDOUT_DAYS)
        mae = float(np.mean(np.abs(pred.to_numpy() - test.to_numpy())))
        rmse = float(np.sqrt(np.mean((pred.to_numpy() - test.to_numpy()) ** 2)))

        full_model = _fit_series(series)
        channels[channel] = ChannelSeries(history=series, fitted=full_model)
        metrics[channel] = {"mae": round(mae, 2), "rmse": round(rmse, 2)}

    return SalesForecastState(channels=channels, metrics=metrics)


def forecast(state: SalesForecastState, channel: str, horizon_days: int = DEFAULT_HORIZON_DAYS) -> SalesForecastResponse:
    if channel not in state.channels:
        raise KeyError(channel)
    cs = state.channels[channel]

    history_points = [
        TimeSeriesPoint(ts=ts.date().isoformat(), value=float(v)) for ts, v in cs.history.tail(90).items()
    ]

    pred = cs.fitted.forecast(horizon_days)
    resid_std = float(np.std(cs.fitted.resid)) if hasattr(cs.fitted, "resid") else 0.0
    last_date = cs.history.index[-1]
    forecast_points = [
        TimeSeriesPoint(
            ts=(last_date + timedelta(days=i)).date().isoformat(),
            value=float(max(value, 0.0)),
            p10=float(max(value - Z80 * resid_std, 0.0)),
            p90=float(max(value + Z80 * resid_std, 0.0)),
        )
        for i, value in enumerate(pred.to_numpy(), start=1)
    ]

    return SalesForecastResponse(
        source="demo",
        model=MODEL_NAME,
        channel=channel,
        history=history_points,
        forecast=forecast_points,
        metrics=state.metrics[channel],
    )
