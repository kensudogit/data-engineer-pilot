from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SourcedModel(BaseModel):
    """Every response schema in this app extends this. `source` must always
    be set explicitly by the service that built the response — never
    defaulted — so a "bigquery" label can never accidentally describe a
    demo-mode result (see config.py's demo_mode docstring)."""

    source: Literal["demo", "bigquery"]
    model: str


class Metrics(BaseModel):
    """Generic metrics bag; each use case documents which keys it sets."""

    values: dict[str, float]


class TimeSeriesPoint(BaseModel):
    ts: str
    value: float
    p10: float | None = None
    p90: float | None = None
