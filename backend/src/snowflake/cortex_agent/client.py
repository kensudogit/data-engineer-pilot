"""Cortex Agent REST API client.

Buffers the real SSE streaming response (POST /api/v2/cortex/agent:run) into
a single JSON reply — a deliberate simplification, not a faithful proxy of
the real streaming API, since this project has no existing streaming
endpoint to extend. Never executed against a real account this session —
see agent_config.py's docstring on why this is the lowest-confidence SQL/API
surface in this project; re-verify the event-stream shape against
https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run
before a real deployment.
"""

from __future__ import annotations

import json

from src.config import Settings
from src.snowflake.cortex_agent.agent_config import build_agent_payload


class CortexAgentNotConfiguredError(RuntimeError):
    """Raised when SNOWFLAKE_PAT isn't set. Only ever raised by
    api/cortex_agent.py's snowflake-mode branch — never affects the
    demo/bigquery execution paths."""


def ask_cortex_agent(question: str, settings: Settings) -> dict:
    """Returns {"answer": str, "citations": list[dict]}."""
    if not settings.snowflake_pat:
        raise CortexAgentNotConfiguredError(
            "SNOWFLAKE_PAT is not set — required for Cortex Agent's REST API (see README known limitations)"
        )

    import httpx  # noqa: PLC0415

    url = f"https://{settings.snowflake_account}.snowflakecomputing.com/api/v2/cortex/agent:run"
    payload = build_agent_payload(question, settings)
    headers = {
        "Authorization": f"Bearer {settings.snowflake_pat}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    answer_parts: list[str] = []
    citations: list[dict] = []
    with httpx.stream("POST", url, json=payload, headers=headers, timeout=60.0) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            data_str = line[len("data:") :].strip()
            if data_str == "[DONE]":
                break
            event = json.loads(data_str)
            for block in event.get("delta", {}).get("content", []):
                if block.get("type") == "text":
                    answer_parts.append(block.get("text", ""))
                elif block.get("type") == "citation":
                    citations.append(block)

    return {"answer": "".join(answer_parts), "citations": citations}
