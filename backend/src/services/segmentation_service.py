from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from src.data import features
from src.data.synth import SyntheticDataset
from src.schemas.segmentation import ClusterSummary, SegmentationResponse, SegmentCustomer

MODEL_NAME = "customer_segments_model"
FEATURE_COLS = ["recency_days", "frequency_90d", "monetary_90d", "avg_order_value", "tenure_days"]
N_CLUSTERS = 4


@dataclass
class SegmentationState:
    customers: pd.DataFrame  # with cluster_id assigned
    cluster_labels: dict[int, str]
    metrics: dict[str, float]


_RANK_LABELS = ["VIP", "優良顧客", "一般顧客", "休眠リスク"]


def _label_clusters(centers: pd.DataFrame) -> dict[int, str]:
    """Heuristic display labels derived from centroid characteristics —
    purely cosmetic, not part of the clustering model itself.

    Assigns one label per cluster by monetary_90d rank (highest spend =
    "VIP", lowest = "休眠リスク"), which guarantees every cluster gets a
    distinct label — a threshold-based rule (e.g. "recency_rank >= 3 ->
    休眠リスク") can accidentally match more than one cluster and leave two
    segments with an identical name, which is exactly what happened during
    manual verification (two different clusters both labeled 休眠リスク).
    """
    ordered = centers["monetary_90d"].sort_values(ascending=False)
    labels: dict[int, str] = {}
    for rank, cluster_id in enumerate(ordered.index):
        label_index = min(rank, len(_RANK_LABELS) - 1)
        labels[cluster_id] = _RANK_LABELS[label_index]
    return labels


def prepare(dataset: SyntheticDataset) -> SegmentationState:
    snapshot = features.customer_features(dataset, dataset.as_of_date)
    X = snapshot[FEATURE_COLS]

    X_scaled = StandardScaler().fit_transform(X)
    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    cluster_ids = kmeans.fit_predict(X_scaled)

    sil = float(silhouette_score(X_scaled, cluster_ids)) if len(set(cluster_ids)) > 1 else float("nan")

    result = snapshot.copy()
    result["cluster_id"] = cluster_ids
    centers = result.groupby("cluster_id")[FEATURE_COLS].mean()
    cluster_labels = _label_clusters(centers)

    return SegmentationState(customers=result, cluster_labels=cluster_labels, metrics={"silhouette_score": round(sil, 4)})


def segments(state: SegmentationState) -> SegmentationResponse:
    clusters = [
        ClusterSummary(
            cluster_id=int(cid),
            label=state.cluster_labels.get(int(cid), f"Cluster {cid}"),
            size=int(len(g)),
            avg_recency_days=round(float(g["recency_days"].mean()), 1),
            avg_frequency_90d=round(float(g["frequency_90d"].mean()), 1),
            avg_monetary_90d=round(float(g["monetary_90d"].mean()), 1),
        )
        for cid, g in state.customers.groupby("cluster_id")
    ]

    customers = [
        SegmentCustomer(
            customer_id=r["customer_id"],
            cluster_id=int(r["cluster_id"]),
            recency_days=float(r["recency_days"]),
            frequency_90d=float(r["frequency_90d"]),
            monetary_90d=float(r["monetary_90d"]),
        )
        for _, r in state.customers.iterrows()
    ]

    return SegmentationResponse(
        source="demo", model=MODEL_NAME, clusters=clusters, customers=customers, metrics=state.metrics
    )
