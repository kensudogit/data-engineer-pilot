from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd
from sklearn.ensemble import IsolationForest

from src.data import features
from src.data.synth import SyntheticDataset
from src.schemas.anomaly import AnomalyOrder, AnomalyResponse

MODEL_NAME = "order_anomaly_model"
FEATURE_COLS = ["order_amount", "item_count", "discount_pct", "avg_unit_price", "hours_since_last_order"]
CONTAMINATION = 0.015


@dataclass
class AnomalyState:
    # Keeps is_injected_anomaly (generator-internal, test-only) — never
    # forwarded to the API schema layer. See features.order_transaction_features.
    orders: pd.DataFrame
    metrics: dict[str, float]


def prepare(dataset: SyntheticDataset) -> AnomalyState:
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
    if total_injected:
        true_positives = int((result["is_anomaly"] & result["is_injected_anomaly"]).sum())
        metrics["recall_on_injected_anomalies"] = round(true_positives / total_injected, 4)

    return AnomalyState(orders=result, metrics=metrics)


def detect(state: AnomalyState, window_days: int | None = None, limit: int = 100) -> AnomalyResponse:
    df = state.orders
    if window_days is not None:
        cutoff = df["order_date"].max() - timedelta(days=window_days)
        df = df[df["order_date"] >= cutoff]

    df = df.sort_values("score", ascending=False).head(limit)

    anomalies = [
        AnomalyOrder(
            order_id=r["order_id"],
            order_date=r["order_date"].isoformat(),
            customer_id=r["customer_id"],
            order_amount=float(r["order_amount"]),
            score=round(float(r["score"]), 4),
            is_anomaly=bool(r["is_anomaly"]),
        )
        for _, r in df.iterrows()
    ]

    return AnomalyResponse(source="demo", model=MODEL_NAME, anomalies=anomalies, metrics=state.metrics)
