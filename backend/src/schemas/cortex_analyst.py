from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CortexAnalystRequest(BaseModel):
    question: str


class CortexAnalystResponse(BaseModel):
    """Deliberately does NOT extend SourcedModel (schemas/common.py):
    Cortex Analyst has no demo/bigquery equivalent at all — not even a
    degraded one — so `source` here is always the literal "snowflake"
    rather than a 3-way choice. When this feature isn't usable
    (execution_mode != "snowflake"), the API returns 503 instead of ever
    constructing this schema with a misleading value.
    """

    source: Literal["snowflake"] = "snowflake"
    question: str
    generated_sql: str | None = None
    answer: str
