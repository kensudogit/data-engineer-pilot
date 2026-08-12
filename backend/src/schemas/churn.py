from __future__ import annotations

from pydantic import BaseModel

from src.schemas.common import SourcedModel


class ChurnCustomer(BaseModel):
    customer_id: str
    churn_probability: float
    risk_tier: str  # "low" | "medium" | "high"
    plan_type: str
    region: str
    tenure_days: int


class ChurnResponse(SourcedModel):
    customers: list[ChurnCustomer]
    metrics: dict[str, float]
