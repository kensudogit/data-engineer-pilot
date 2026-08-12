from __future__ import annotations

from pydantic import BaseModel

from src.schemas.common import SourcedModel


class UseCaseSummary(BaseModel):
    key: str
    label: str
    headline: str
    detail: str


class OverviewResponse(SourcedModel):
    generated_at: str
    total_customers: int
    active_customers: int
    total_orders: int
    total_revenue: float
    summaries: list[UseCaseSummary]
