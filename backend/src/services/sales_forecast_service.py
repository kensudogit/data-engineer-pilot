from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.config import Settings, get_settings
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
    # Keyed by channel — computed once per channel at prepare()-time (using
    # DEFAULT_HORIZON_DAYS regardless of what horizon_days a caller later
    # requests) rather than per-request, so a real Cortex COMPLETE call
    # never fires on the request path. See forecast()'s use of this.
    ai_insights: dict[str, str]
    ai_insight_generated_by: Literal["template", "cortex"]
    # "snowflake" state carries no fitted statsmodels object (ChannelSeries.
    # fitted is None) — forecast() branches on this to call the live
    # sales_forecast_model!FORECAST() serving query per request instead
    # (unlike the AI insight text, re-querying a Cortex ML Function's
    # forecast per request at the caller's chosen horizon_days is the
    # expected usage pattern, not a cost concern the way repeated LLM
    # COMPLETE calls would be).
    source: Literal["demo", "snowflake"]


def _fit_series(series: pd.Series):
    return ExponentialSmoothing(
        series, trend="add", seasonal="add", seasonal_periods=SEASONAL_PERIOD, initialization_method="estimated"
    ).fit()


def prepare(dataset: SyntheticDataset) -> SalesForecastState:
    settings = get_settings()
    if settings.execution_mode == "snowflake":
        return _prepare_snowflake(dataset, settings)
    return _prepare_demo(dataset)


def _prepare_demo(dataset: SyntheticDataset) -> SalesForecastState:
    """Trains one Holt-Winters model per channel once, at startup — services
    never refit per-request (see the plan's dataset-consistency note)."""
    daily = features.daily_sales(dataset)
    channels: dict[str, ChannelSeries] = {}
    metrics: dict[str, dict[str, float]] = {}
    ai_insights: dict[str, str] = {}

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
        ai_insights[channel] = (
            f"直近{HOLDOUT_DAYS}日のホールドアウト検証でMAE {mae:,.0f}円・RMSE {rmse:,.0f}円のHolt-Wintersモデルにより、"
            f"{channel}チャネルの今後{DEFAULT_HORIZON_DAYS}日間の売上を予測しました。"
        )

    return SalesForecastState(
        channels=channels, metrics=metrics, ai_insights=ai_insights, ai_insight_generated_by="template", source="demo"
    )


def _prepare_snowflake(dataset: SyntheticDataset, settings: Settings) -> SalesForecastState:
    """Queries the sales_forecast_model Cortex ML Function (SNOWFLAKE.ML.FORECAST)
    already created by provision_snowflake.py --create-models — never
    CREATEs it inline here. Never executed/verified this session (no live
    Snowflake account); the exact result-column shape of `!FORECAST()` and
    `!SHOW_EVALUATION_METRICS()` should be re-checked against current
    Snowflake docs before relying on this against a real account (see the
    plan's note on Cortex ML Functions argument/result drift risk).
    """
    from src.snowflake.client import get_session  # noqa: PLC0415
    from src.snowflake.cortex.insight import build_prompt_sales_forecast, generate_insight  # noqa: PLC0415

    session = get_session()

    history_df = session.table("mart.daily_sales_view").to_pandas()
    history_df.columns = [c.lower() for c in history_df.columns]

    eval_rows = session.sql("CALL sales_forecast_model!SHOW_EVALUATION_METRICS()").collect()
    eval_df = pd.DataFrame([r.as_dict() for r in eval_rows])
    eval_df.columns = [c.lower() for c in eval_df.columns]

    channels: dict[str, ChannelSeries] = {}
    metrics: dict[str, dict[str, float]] = {}
    ai_insights: dict[str, str] = {}

    for channel in sorted(history_df["channel"].unique()):
        sub = history_df[history_df["channel"] == channel].sort_values("order_date")
        series = pd.Series(
            sub["total_amount"].to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(sub["order_date"]))
        ).asfreq("D", fill_value=0.0)
        channels[channel] = ChannelSeries(history=series, fitted=None)

        row = eval_df[eval_df["series_id"] == channel] if "series_id" in eval_df.columns else eval_df
        mae = float(row["mae"].iloc[0]) if "mae" in row.columns and len(row) else float("nan")
        rmse = float(row["rmse"].iloc[0]) if "rmse" in row.columns and len(row) else float("nan")
        metrics[channel] = {"mae": round(mae, 2), "rmse": round(rmse, 2)}
        ai_insights[channel] = generate_insight(
            session,
            build_prompt_sales_forecast(channel, DEFAULT_HORIZON_DAYS, mae, rmse),
            settings.cortex_model,
        )

    return SalesForecastState(
        channels=channels, metrics=metrics, ai_insights=ai_insights, ai_insight_generated_by="cortex", source="snowflake"
    )


def _forecast_points_demo(cs: ChannelSeries, horizon_days: int) -> list[TimeSeriesPoint]:
    pred = cs.fitted.forecast(horizon_days)
    resid_std = float(np.std(cs.fitted.resid)) if hasattr(cs.fitted, "resid") else 0.0
    last_date = cs.history.index[-1]
    return [
        TimeSeriesPoint(
            ts=(last_date + timedelta(days=i)).date().isoformat(),
            value=float(max(value, 0.0)),
            p10=float(max(value - Z80 * resid_std, 0.0)),
            p90=float(max(value + Z80 * resid_std, 0.0)),
        )
        for i, value in enumerate(pred.to_numpy(), start=1)
    ]


def _forecast_points_snowflake(channel: str, horizon_days: int) -> list[TimeSeriesPoint]:
    """Calls the pre-provisioned sales_forecast_model!FORECAST() serving
    query at the caller's requested horizon — never executed/verified this
    session, see _prepare_snowflake's docstring on result-shape risk."""
    from src.snowflake.client import get_session  # noqa: PLC0415

    session = get_session()
    rows = session.sql(
        "CALL sales_forecast_model!FORECAST(SERIES_VALUE => ?, FORECASTING_PERIODS => ?, "
        "CONFIG_OBJECT => {'prediction_interval': 0.8})",
        params=[channel, horizon_days],
    ).collect()
    df = pd.DataFrame([r.as_dict() for r in rows])
    df.columns = [c.lower() for c in df.columns]
    return [
        TimeSeriesPoint(
            ts=str(r["ts"]),
            value=float(max(r["forecast"], 0.0)),
            p10=float(max(r.get("lower_bound", r["forecast"]), 0.0)),
            p90=float(max(r.get("upper_bound", r["forecast"]), 0.0)),
        )
        for _, r in df.iterrows()
    ]


def forecast(state: SalesForecastState, channel: str, horizon_days: int = DEFAULT_HORIZON_DAYS) -> SalesForecastResponse:
    if channel not in state.channels:
        raise KeyError(channel)
    cs = state.channels[channel]

    history_points = [
        TimeSeriesPoint(ts=ts.date().isoformat(), value=float(v)) for ts, v in cs.history.tail(90).items()
    ]

    if state.source == "snowflake":
        forecast_points = _forecast_points_snowflake(channel, horizon_days)
    else:
        forecast_points = _forecast_points_demo(cs, horizon_days)

    return SalesForecastResponse(
        source=state.source,
        model=MODEL_NAME,
        channel=channel,
        history=history_points,
        forecast=forecast_points,
        metrics=state.metrics[channel],
        ai_insight=state.ai_insights.get(channel),
        ai_insight_generated_by=state.ai_insight_generated_by,
    )
