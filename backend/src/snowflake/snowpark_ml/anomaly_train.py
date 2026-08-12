"""Snowpark ML equivalent of anomaly_service.py's scikit-learn IsolationForest.

Cortex ML Functions' SNOWFLAKE.ML.ANOMALY_DETECTION is a time-series
function (one numeric metric observed over a timestamp axis) and does not
fit this use case's shape: per-order, multivariate, non-sequential tabular
anomaly detection over order_amount/item_count/discount_pct/avg_unit_price/
hours_since_last_order. This mirrors exactly why the BigQuery path chose
AUTOENCODER over a KMEANS-distance heuristic (see
backend/src/bigquery/ml/04_anomaly_model.sql's comment) — the right tool
here is Snowpark ML's Modeling API, using the same algorithm
(IsolationForest) and the same contamination rate as the demo path, for
numeric parity between the two.
"""

from __future__ import annotations

import pandas as pd

from src.services.anomaly_service import CONTAMINATION, FEATURE_COLS

_PASSTHROUGH_COLS = ["order_id", "order_date", "customer_id", *FEATURE_COLS]  # order_amount is already in FEATURE_COLS


def train(session, feature_view: str = "mart.order_transaction_features_view") -> pd.DataFrame:
    """Fits IsolationForest against order_transaction_features and returns a
    pandas DataFrame with order_id/order_date/customer_id/order_amount plus
    `score` (higher = more anomalous, same sign convention as
    anomaly_service.py) and `is_anomaly` (bool).
    """
    from snowflake.ml.modeling.ensemble import IsolationForest  # noqa: PLC0415

    df = session.table(feature_view)

    model = IsolationForest(
        contamination=CONTAMINATION,
        random_state=42,
        n_estimators=200,
        input_cols=FEATURE_COLS,
        output_cols=["prediction"],
        passthrough_cols=_PASSTHROUGH_COLS,
    )
    model.fit(df)

    # decision_function appends one new column prefixed "decision_function_"
    # (sklearn convention: higher = more normal); locate it by set-difference
    # rather than hardcoding its exact suffix, since this path can't be
    # exercised against a live account this session to confirm it.
    before_cols = set(df.columns)
    scored = model.decision_function(df)
    raw_score_col = next(c for c in scored.columns if c not in before_cols)

    scored = model.predict(scored)

    result = scored.to_pandas()
    result.columns = [c.lower() for c in result.columns]
    raw_score_col = raw_score_col.lower()

    result["score"] = -result[raw_score_col]  # flip so higher = more anomalous
    result["is_anomaly"] = result["prediction"] == -1
    return result
