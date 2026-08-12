from __future__ import annotations

from pydantic import BaseModel

from src.schemas.common import SourcedModel, TimeSeriesPoint


class ProductOption(BaseModel):
    product_id: str
    name: str


class DemandForecastResponse(SourcedModel):
    product_id: str
    product_name: str
    history: list[TimeSeriesPoint]
    forecast: list[TimeSeriesPoint]
    metrics: dict[str, float]


class ProductListResponse(SourcedModel):
    products: list[ProductOption]
