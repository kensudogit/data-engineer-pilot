from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

import pandas as pd
from sklearn.ensemble import IsolationForest

from src.config import Settings, get_settings
from src.data import features
from src.data.synth import SyntheticDataset
from src.schemas.anomaly import AnomalyOrder, AnomalyResponse

MODEL_NAME = "order_anomaly_model"
FEATURE_COLS = ["order_amount", "item_count", "discount_pct", "avg_unit_price", "hours_since_last_order"]
CONTAMINATION = 0.015


@dataclass
class AnomalyState:
    # Keeps is_injected_anomaly (generator-internal, test-only) on the demo
    # path — never forwarded to the API schema layer. See
    # features.order_transaction_features. The snowflake path's orders
    # DataFrame never has this column at all (it doesn't exist in the real
    # mart.order_transaction_features table, only in the local synthetic
    # generator), so there's nothing to accidentally leak there either.
    orders: pd.DataFrame
    metrics: dict[str, float]
    ai_insight: str
    ai_insight_generated_by: Literal["template", "cortex"]
    source: Literal["demo", "snowflake"]


def prepare(dataset: SyntheticDataset) -> AnomalyState:
    settings = get_settings()
    if settings.execution_mode == "snowflake":
        return _prepare_snowflake(dataset, settings)
    return _prepare_demo(dataset)


def _prepare_demo(dataset: SyntheticDataset) -> AnomalyState:
    txns = features.order_transaction_features(dataset)
    X = txns[FEATURE_COLS].fillna(0.0)

    model = IsolationForest(contamination=CONTAMINATION, random_state=42, n_estimators=200)
    model.fit(X)
    raw_scores = model.decision_function(X)  # higher = more normal
    is_anomaly = model.predict(X) == -1

    result = txns.copy()
    result["score"] = -raw_scores  # flip so higher = more anomalous
    result["is_anomaly"] = is_anomaly

    metrics: dict[str, float] = {"contamination": CONTAMINATION}
    total_injected = int(result["is_injected_anomaly"].sum())
    recall = None
    if total_injected:
        true_positives = int((result["is_anomaly"] & result["is_injected_anomaly"]).sum())
        recall = round(true_positives / total_injected, 4)
        metrics["recall_on_injected_anomalies"] = recall

    detected_count = int(result["is_anomaly"].sum())
    recall_text = f"注入検証用異常に対する再現率は{recall * 100:.1f}%です。" if recall is not None else ""
    ai_insight = (
        f"IsolationForest（想定異常率{CONTAMINATION * 100:.1f}%）により{detected_count}件の取引を"
        f"異常スコアリングしました。{recall_text}"
    )

    return AnomalyState(
        orders=result, metrics=metrics, ai_insight=ai_insight, ai_insight_generated_by="template", source="demo"
    )


def _prepare_snowflake(dataset: SyntheticDataset, settings: Settings) -> AnomalyState:
    """Trains via Snowpark ML's IsolationForest
    (src/snowflake/snowpark_ml/anomaly_train.py) — see that module's
    docstring on why Cortex ML Functions' SNOWFLAKE.ML.ANOMALY_DETECTION
    (a time-series function) doesn't fit this per-order, multivariate use
    case. Never executed/verified this session (no live Snowflake account).
    No recall_on_injected_anomalies metric here — the injected-anomaly flag
    is a local synthetic-generator-only concept, absent from the real
    mart.order_transaction_features table.
    """
    from src.snowflake.client import get_session  # noqa: PLC0415
    from src.snowflake.cortex.insight import build_prompt_anomaly, generate_insight  # noqa: PLC0415
    from src.snowflake.snowpark_ml.anomaly_train import train as snowpark_train  # noqa: PLC0415

    session = get_session()
    result = snowpark_train(session)

    metrics: dict[str, float] = {"contamination": CONTAMINATION}
    detected_count = int(result["is_anomaly"].sum())
    ai_insight = generate_insight(
        session, build_prompt_anomaly(CONTAMINATION, detected_count, None), settings.cortex_model
    )

    return AnomalyState(
        orders=result, metrics=metrics, ai_insight=ai_insight, ai_insight_generated_by="cortex", source="snowflake"
    )


def detect(state: AnomalyState, window_days: int | None = None, limit: int = 100) -> AnomalyResponse:
    df = state.orders
    if window_days is not None:
        cutoff = df["order_date"].max() - timedelta(days=window_days)
        df = df[df["order_date"] >= cutoff]

    df = df.sort_values("score", ascending=False).head(limit)

    anomalies = [
        AnomalyOrder(
            order_id=r["order_id"],
            order_date=r["order_date"].isoformat() if hasattr(r["order_date"], "isoformat") else str(r["order_date"]),
            customer_id=r["customer_id"],
            order_amount=float(r["order_amount"]),
            score=round(float(r["score"]), 4),
            is_anomaly=bool(r["is_anomaly"]),
        )
        for _, r in df.iterrows()
    ]

    return AnomalyResponse(
        source=state.source,
        model=MODEL_NAME,
        anomalies=anomalies,
        metrics=state.metrics,
        ai_insight=state.ai_insight,
        ai_insight_generated_by=state.ai_insight_generated_by,
    )
