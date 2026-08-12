from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SourcedModel(BaseModel):
    """Every response schema in this app extends this. `source` must always
    be set explicitly by the service that built the response — never
    defaulted — so a "bigquery"/"snowflake" label can never accidentally
    describe a demo-mode result (see config.py's execution_mode docstring).

    `ai_insight` is an optional natural-language summary of the result.
    List-only responses (ChannelListResponse, ProductListResponse) leave it
    unset — there's nothing to narrate. `ai_insight_generated_by` discloses
    how the text was produced: "cortex" only when a real
    SNOWFLAKE.CORTEX.COMPLETE call produced it (execution_mode="snowflake");
    "template" for the demo/bigquery paths, where it's assembled from
    already-computed metrics by an f-string, never phrased as if an AI
    wrote it — the same "never let a fake result look real" principle the
    `source` field enforces, applied to text instead of numbers.
    """

    source: Literal["demo", "bigquery", "snowflake"]
    model: str
    ai_insight: str | None = None
    ai_insight_generated_by: Literal["template", "cortex"] | None = None


class Metrics(BaseModel):
    """Generic metrics bag; each use case documents which keys it sets."""

    values: dict[str, float]


class TimeSeriesPoint(BaseModel):
    ts: str
    value: float
    p10: float | None = None
    p90: float | None = None
