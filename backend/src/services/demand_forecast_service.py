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
from src.schemas.demand_forecast import DemandForecastResponse, ProductOption

MODEL_NAME = "demand_forecast_model"
SEASONAL_PERIOD = 7
HOLDOUT_DAYS = 14
Z80 = 1.2816
MIN_HISTORY_POINTS = SEASONAL_PERIOD * 2 + HOLDOUT_DAYS


@dataclass
class ProductSeries:
    product_id: str
    name: str
    history: pd.Series
    fitted: object


@dataclass
class DemandForecastState:
    products: dict[str, ProductSeries]
    metrics: dict[str, dict[str, float]]
    # Keyed by product_id — same "computed once at prepare()-time, not
    # per-request" rule as sales_forecast_service.SalesForecastState.
    # ai_insight_generated_by is per-product too, same reasoning as
    # sales_forecast_service (independent OpenAI success/failure per item).
    ai_insights: dict[str, str]
    ai_insight_generated_by: dict[str, Literal["template", "cortex", "openai"]]
    source: Literal["demo", "snowflake"]


def _fit_series(series: pd.Series):
    return ExponentialSmoothing(
        series, trend="add", seasonal="add", seasonal_periods=SEASONAL_PERIOD, initialization_method="estimated"
    ).fit()


def prepare(dataset: SyntheticDataset) -> DemandForecastState:
    settings = get_settings()
    if settings.execution_mode == "snowflake":
        return _prepare_snowflake(dataset, settings)
    return _prepare_demo(dataset, settings)


def _prepare_demo(dataset: SyntheticDataset, settings: Settings) -> DemandForecastState:
    """Fits one Holt-Winters model per (already top-N-limited) product once,
    at startup — see features.daily_product_demand for the top-N filter.

    If OPENAI_API_KEY is set, this also means up to 20 OpenAI calls at
    startup (one per top-N product) — acceptable for a pilot with
    gpt-4o-mini, but worth knowing if you're watching API usage; see
    README's cost note.
    """
    from src.ai.openai_client import enhance_with_openai  # noqa: PLC0415
    from src.ai.prompts import build_prompt_demand_forecast  # noqa: PLC0415

    demand = features.daily_product_demand(dataset)
    product_names = dataset.products.set_index("product_id")["name"]

    products: dict[str, ProductSeries] = {}
    metrics: dict[str, dict[str, float]] = {}
    ai_insights: dict[str, str] = {}
    ai_insight_generated_by: dict[str, Literal["template", "cortex", "openai"]] = {}

    for product_id in sorted(demand["product_id"].unique()):
        sub = demand[demand["product_id"] == product_id].sort_values("order_date")
        series = pd.Series(
            sub["quantity_sold"].to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(sub["order_date"]))
        ).asfreq("D", fill_value=0.0)

        if len(series) < MIN_HISTORY_POINTS:
            continue

        train, test = series.iloc[:-HOLDOUT_DAYS], series.iloc[-HOLDOUT_DAYS:]
        holdout_model = _fit_series(train)
        pred = holdout_model.forecast(HOLDOUT_DAYS)
        mae = float(np.mean(np.abs(pred.to_numpy() - test.to_numpy())))
        rmse = float(np.sqrt(np.mean((pred.to_numpy() - test.to_numpy()) ** 2)))

        full_model = _fit_series(series)
        name = product_names.get(product_id, product_id)
        products[product_id] = ProductSeries(product_id=product_id, name=name, history=series, fitted=full_model)
        metrics[product_id] = {"mae": round(mae, 2), "rmse": round(rmse, 2)}
        template_insight = (
            f"{name}の需要をHolt-Wintersモデルで予測しました（ホールドアウトMAE {mae:.1f}個）。"
            f"計算コストの都合で上位20商品に限定しています。"
        )
        ai_insights[product_id], ai_insight_generated_by[product_id] = enhance_with_openai(
            template_insight, build_prompt_demand_forecast(name, HOLDOUT_DAYS, mae), settings
        )

    return DemandForecastState(
        products=products,
        metrics=metrics,
        ai_insights=ai_insights,
        ai_insight_generated_by=ai_insight_generated_by,
        source="demo",
    )


def _prepare_snowflake(dataset: SyntheticDataset, settings: Settings) -> DemandForecastState:
    """Queries the demand_forecast_model Cortex ML Function (SNOWFLAKE.ML.FORECAST)
    already created by provision_snowflake.py --create-models. Never
    executed/verified this session — see sales_forecast_service's
    _prepare_snowflake docstring on result-shape risk, which this mirrors."""
    from src.snowflake.client import get_session  # noqa: PLC0415
    from src.snowflake.cortex.insight import build_prompt_demand_forecast, generate_insight  # noqa: PLC0415

    session = get_session()

    history_df = session.table("mart.daily_product_demand_view").to_pandas()
    history_df.columns = [c.lower() for c in history_df.columns]

    product_names = dataset.products.set_index("product_id")["name"]

    eval_rows = session.sql("CALL demand_forecast_model!SHOW_EVALUATION_METRICS()").collect()
    eval_df = pd.DataFrame([r.as_dict() for r in eval_rows])
    eval_df.columns = [c.lower() for c in eval_df.columns]

    products: dict[str, ProductSeries] = {}
    metrics: dict[str, dict[str, float]] = {}
    ai_insights: dict[str, str] = {}
    ai_insight_generated_by: dict[str, Literal["template", "cortex", "openai"]] = {}

    for product_id in sorted(history_df["product_id"].unique()):
        sub = history_df[history_df["product_id"] == product_id].sort_values("order_date")
        series = pd.Series(
            sub["quantity_sold"].to_numpy(), index=pd.DatetimeIndex(pd.to_datetime(sub["order_date"]))
        ).asfreq("D", fill_value=0.0)
        name = product_names.get(product_id, product_id)
        products[product_id] = ProductSeries(product_id=product_id, name=name, history=series, fitted=None)

        row = eval_df[eval_df["series_id"] == product_id] if "series_id" in eval_df.columns else eval_df
        mae = float(row["mae"].iloc[0]) if "mae" in row.columns and len(row) else float("nan")
        rmse = float(row["rmse"].iloc[0]) if "rmse" in row.columns and len(row) else float("nan")
        metrics[product_id] = {"mae": round(mae, 2), "rmse": round(rmse, 2)}
        ai_insights[product_id] = generate_insight(
            session, build_prompt_demand_forecast(name, HOLDOUT_DAYS, mae), settings.cortex_model
        )
        ai_insight_generated_by[product_id] = "cortex"

    return DemandForecastState(
        products=products,
        metrics=metrics,
        ai_insights=ai_insights,
        ai_insight_generated_by=ai_insight_generated_by,
        source="snowflake",
    )


def list_products(state: DemandForecastState) -> list[ProductOption]:
    return [ProductOption(product_id=p.product_id, name=p.name) for p in state.products.values()]


def _forecast_points_demo(ps: ProductSeries, horizon_days: int) -> list[TimeSeriesPoint]:
    pred = ps.fitted.forecast(horizon_days)
    resid_std = float(np.std(ps.fitted.resid)) if hasattr(ps.fitted, "resid") else 0.0
    last_date = ps.history.index[-1]
    return [
        TimeSeriesPoint(
            ts=(last_date + timedelta(days=i)).date().isoformat(),
            value=float(max(value, 0.0)),
            p10=float(max(value - Z80 * resid_std, 0.0)),
            p90=float(max(value + Z80 * resid_std, 0.0)),
        )
        for i, value in enumerate(pred.to_numpy(), start=1)
    ]


def _forecast_points_snowflake(product_id: str, horizon_days: int) -> list[TimeSeriesPoint]:
    from src.snowflake.client import get_session  # noqa: PLC0415

    session = get_session()
    rows = session.sql(
        "CALL demand_forecast_model!FORECAST(SERIES_VALUE => ?, FORECASTING_PERIODS => ?, "
        "CONFIG_OBJECT => {'prediction_interval': 0.8})",
        params=[product_id, horizon_days],
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


def forecast(state: DemandForecastState, product_id: str, horizon_days: int = HOLDOUT_DAYS) -> DemandForecastResponse:
    if product_id not in state.products:
        raise KeyError(product_id)
    ps = state.products[product_id]

    history_points = [
        TimeSeriesPoint(ts=ts.date().isoformat(), value=float(v)) for ts, v in ps.history.tail(90).items()
    ]

    if state.source == "snowflake":
        forecast_points = _forecast_points_snowflake(product_id, horizon_days)
    else:
        forecast_points = _forecast_points_demo(ps, horizon_days)

    return DemandForecastResponse(
        source=state.source,
        model=MODEL_NAME,
        product_id=product_id,
        product_name=ps.name,
        history=history_points,
        forecast=forecast_points,
        metrics=state.metrics[product_id],
        ai_insight=state.ai_insights.get(product_id),
        ai_insight_generated_by=state.ai_insight_generated_by.get(product_id),
    )
