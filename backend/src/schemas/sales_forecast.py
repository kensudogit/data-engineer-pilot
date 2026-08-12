from __future__ import annotations

from src.schemas.common import SourcedModel, TimeSeriesPoint


class SalesForecastResponse(SourcedModel):
    channel: str
    history: list[TimeSeriesPoint]
    forecast: list[TimeSeriesPoint]
    metrics: dict[str, float]


class ChannelListResponse(SourcedModel):
    channels: list[str]
