from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

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


def _fit_series(series: pd.Series):
    return ExponentialSmoothing(
        series, trend="add", seasonal="add", seasonal_periods=SEASONAL_PERIOD, initialization_method="estimated"
    ).fit()


def prepare(dataset: SyntheticDataset) -> DemandForecastState:
    """Fits one Holt-Winters model per (already top-N-limited) product once,
    at startup — see features.daily_product_demand for the top-N filter."""
    demand = features.daily_product_demand(dataset)
    product_names = dataset.products.set_index("product_id")["name"]

    products: dict[str, ProductSeries] = {}
    metrics: dict[str, dict[str, float]] = {}

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
        products[product_id] = ProductSeries(
            product_id=product_id, name=product_names.get(product_id, product_id), history=series, fitted=full_model
        )
        metrics[product_id] = {"mae": round(mae, 2), "rmse": round(rmse, 2)}

    return DemandForecastState(products=products, metrics=metrics)


def list_products(state: DemandForecastState) -> list[ProductOption]:
    return [ProductOption(product_id=p.product_id, name=p.name) for p in state.products.values()]


def forecast(state: DemandForecastState, product_id: str, horizon_days: int = HOLDOUT_DAYS) -> DemandForecastResponse:
    if product_id not in state.products:
        raise KeyError(product_id)
    ps = state.products[product_id]

    history_points = [
        TimeSeriesPoint(ts=ts.date().isoformat(), value=float(v)) for ts, v in ps.history.tail(90).items()
    ]

    pred = ps.fitted.forecast(horizon_days)
    resid_std = float(np.std(ps.fitted.resid)) if hasattr(ps.fitted, "resid") else 0.0
    last_date = ps.history.index[-1]
    forecast_points = [
        TimeSeriesPoint(
            ts=(last_date + timedelta(days=i)).date().isoformat(),
            value=float(max(value, 0.0)),
            p10=float(max(value - Z80 * resid_std, 0.0)),
            p90=float(max(value + Z80 * resid_std, 0.0)),
        )
        for i, value in enumerate(pred.to_numpy(), start=1)
    ]

    return DemandForecastResponse(
        source="demo",
        model=MODEL_NAME,
        product_id=product_id,
        product_name=ps.name,
        history=history_points,
        forecast=forecast_points,
        metrics=state.metrics[product_id],
    )
