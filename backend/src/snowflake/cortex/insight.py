"""SNOWFLAKE.CORTEX.COMPLETE-based narrative insight generation.

Only ever called when execution_mode="snowflake" (see each service's
_prepare_snowflake()). Prompt builders live in src/ai/prompts.py, shared
with the OpenAI path (src/ai/openai_client.py) — re-exported here so
existing call sites (`from src.snowflake.cortex.insight import
build_prompt_churn, generate_insight`) keep working unchanged.
"""

from __future__ import annotations

from src.ai.prompts import (
    build_prompt_anomaly as build_prompt_anomaly,
    build_prompt_churn as build_prompt_churn,
    build_prompt_demand_forecast as build_prompt_demand_forecast,
    build_prompt_overview as build_prompt_overview,
    build_prompt_sales_forecast as build_prompt_sales_forecast,
    build_prompt_segmentation as build_prompt_segmentation,
)


def generate_insight(session, prompt: str, model: str) -> str:
    """Runs SNOWFLAKE.CORTEX.COMPLETE(model, prompt) and returns the text.

    A failure here is deliberately allowed to propagate (never caught to
    fall back to a template sentence under a source="snowflake" label) —
    see snowflake/client.py's SnowflakeNotConfiguredError docstring for why.
    """
    row = session.sql("SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS insight", params=[model, prompt]).collect()
    return row[0]["INSIGHT"]
