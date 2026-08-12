"""Snowpark ML equivalent of segmentation_service.py's scikit-learn KMeans.

Cortex ML Functions has no no-code SQL function for clustering, so this
use case is implemented with Snowpark ML's Modeling API instead (a
separate Python library from Cortex, operating on Snowpark/pandas
DataFrames with an sklearn-like fit/predict surface).

This module only trains and returns raw cluster assignments — cluster
*labeling* (VIP/優良顧客/一般顧客/休眠リスク) is deliberately left to the
caller (segmentation_service._prepare_snowflake), which reuses the exact
same `_label_clusters` rank-based function the demo path uses, so the
labeling algorithm exists in exactly one place regardless of which
execution path produced the raw clusters — see segmentation_service.py's
docstring on why threshold-based labeling was replaced with rank-based
labeling (it used to produce duplicate labels across different clusters).
"""

from __future__ import annotations

import pandas as pd

from src.services.segmentation_service import FEATURE_COLS, N_CLUSTERS

_SCALED_COLS = [f"{c}_scaled" for c in FEATURE_COLS]


def train(session, snapshot_view: str = "mart.customer_features_view") -> pd.DataFrame:
    """Fits StandardScaler + KMeans against the latest customer_features
    snapshot and returns a pandas DataFrame with customer_id, the raw
    FEATURE_COLS, and an assigned cluster_id column (all lowercase, matching
    this codebase's pandas column-naming convention — Snowpark returns
    unquoted identifiers uppercased by default).
    """
    from snowflake.ml.modeling.cluster import KMeans  # noqa: PLC0415
    from snowflake.ml.modeling.preprocessing import StandardScaler  # noqa: PLC0415

    df = session.table(snapshot_view).filter(
        f'"snapshot_date" = (SELECT MAX("snapshot_date") FROM {snapshot_view})'
    )

    scaler = StandardScaler(input_cols=FEATURE_COLS, output_cols=_SCALED_COLS)
    scaled = scaler.fit(df).transform(df)

    kmeans = KMeans(
        n_clusters=N_CLUSTERS,
        random_state=42,
        input_cols=_SCALED_COLS,
        output_cols=["cluster_id"],
        passthrough_cols=["customer_id", *FEATURE_COLS],
    )
    kmeans.fit(scaled)
    result = kmeans.predict(scaled).to_pandas()
    result.columns = [c.lower() for c in result.columns]
    return result
