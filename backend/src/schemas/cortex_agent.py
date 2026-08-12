from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class CortexAgentRequest(BaseModel):
    question: str


class CortexAgentResponse(BaseModel):
    """Same non-SourcedModel design as schemas/cortex_analyst.py — Cortex
    Agent has no demo equivalent, so `source` is always the literal
    "snowflake" and the API returns 503 rather than ever constructing this
    with a misleading value."""

    source: Literal["snowflake"] = "snowflake"
    question: str
    answer: str
    citations: list[dict] = []
