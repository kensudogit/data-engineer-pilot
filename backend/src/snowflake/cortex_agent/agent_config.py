"""Cortex Agent request payload builder for POST /api/v2/cortex/agent:run.

LOWEST CONFIDENCE SQL/API SHAPE IN THIS PROJECT — Cortex Agent is Snowflake's
newest and least mature REST surface among everything covered this session.
The `tools`/`tool_resources` split (tools declare only type/name/description;
actual config lives in a separate tool_resources object keyed by that same
name) is documented, but the exact placement of `execution_environment`
(nested under the analyst tool's own tool_resources entry, as done below,
vs. a top-level request field) was not confirmed against a live account.
Re-verify against https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-run
before a real deployment.

Never executed this session — same "correct syntax, undeployed" disclosure
as the rest of this project's Snowflake integration.
"""

from __future__ import annotations

from src.config import Settings

SEARCH_TOOL_NAME = "support_search"
ANALYST_TOOL_NAME = "mart_analyst"


def build_agent_payload(question: str, settings: Settings) -> dict:
    return {
        "messages": [{"role": "user", "content": [{"type": "text", "text": question}]}],
        "tools": [
            {
                "tool_spec": {
                    "type": "cortex_search",
                    "name": SEARCH_TOOL_NAME,
                    "description": "FAQ・運用マニュアル文書を検索する",
                }
            },
            {
                "tool_spec": {
                    "type": "cortex_analyst_text_to_sql",
                    "name": ANALYST_TOOL_NAME,
                    "description": "売上・解約予測・顧客分類・需要予測・異常検知のMARTデータに対する質問をSQLに変換して実行する",
                }
            },
        ],
        "tool_resources": {
            SEARCH_TOOL_NAME: {
                "search_service": f"{settings.snowflake_database}.mart.support_search",
                "title_column": "title",
                "id_column": "doc_id",
            },
            ANALYST_TOOL_NAME: {
                "semantic_model_file": f"@{settings.snowflake_database}.mart.semantic_models/semantic_model.yaml",
                "execution_environment": {"type": "warehouse", "warehouse": settings.snowflake_warehouse},
            },
        },
    }
