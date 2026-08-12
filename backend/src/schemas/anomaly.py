from __future__ import annotations

from pydantic import BaseModel

from src.schemas.common import SourcedModel


class AnomalyOrder(BaseModel):
    order_id: str
    order_date: str
    customer_id: str
    order_amount: float
    score: float
    is_anomaly: bool


class AnomalyResponse(SourcedModel):
    anomalies: list[AnomalyOrder]
    metrics: dict[str, float]
