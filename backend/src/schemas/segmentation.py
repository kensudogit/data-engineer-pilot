from __future__ import annotations

from pydantic import BaseModel

from src.schemas.common import SourcedModel


class SegmentCustomer(BaseModel):
    customer_id: str
    cluster_id: int
    recency_days: float
    frequency_90d: float
    monetary_90d: float


class ClusterSummary(BaseModel):
    cluster_id: int
    label: str
    size: int
    avg_recency_days: float
    avg_frequency_90d: float
    avg_monetary_90d: float


class SegmentationResponse(SourcedModel):
    clusters: list[ClusterSummary]
    customers: list[SegmentCustomer]
    metrics: dict[str, float]
