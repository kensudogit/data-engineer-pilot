"""Cortex Analyst REST API client.

Never executed against a real account this session — no live Snowflake
account, and this project's existing Snowpark session auth (username/
password) doesn't cover Cortex Analyst's REST API, which needs a bearer
token (see config.py's snowflake_pat setting). Re-verify the exact request/
response shape against
https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst
before a real deployment — same "correct syntax, undeployed" disclosure as
the rest of this project's Snowflake integration.
"""

from __future__ import annotations

from src.config import Settings


class CortexAnalystNotConfiguredError(RuntimeError):
    """Raised when SNOWFLAKE_PAT isn't set. Only ever raised by
    api/cortex_analyst.py's snowflake-mode branch — never affects the
    demo/bigquery execution paths."""


def ask_cortex_analyst(question: str, settings: Settings) -> dict:
    """Calls POST /api/v2/cortex/analyst/message and returns
    {"sql": str | None, "answer": str}.

    Response shape per Cortex Analyst's documented API: `message.content`
    is a list of typed blocks — a `"sql"` block carries the generated SQL
    in `statement`, `"text"` blocks carry the natural-language answer.
    """
    if not settings.snowflake_pat:
        raise CortexAnalystNotConfiguredError(
            "SNOWFLAKE_PAT is not set — required for Cortex Analyst's REST API (see README known limitations)"
        )

    import httpx  # noqa: PLC0415

    url = f"https://{settings.snowflake_account}.snowflakecomputing.com/api/v2/cortex/analyst/message"
    payload = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "semantic_model_file": f"@{settings.snowflake_database}.mart.semantic_models/semantic_model.yaml",
    }
    headers = {"Authorization": f"Bearer {settings.snowflake_pat}", "Content-Type": "application/json"}

    response = httpx.post(url, json=payload, headers=headers, timeout=30.0)
    response.raise_for_status()
    data = response.json()

    sql = None
    answer_parts: list[str] = []
    for block in data.get("message", {}).get("content", []):
        if block.get("type") == "sql":
            sql = block.get("statement")
        elif block.get("type") == "text":
            answer_parts.append(block.get("text", ""))

    return {"sql": sql, "answer": "\n".join(answer_parts)}
