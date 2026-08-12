"""Shared SQL-file rendering used by backend/scripts/provision_snowflake.py
and by test_sql_render_utils.py's syntax-safety checks.

Split out from provision_snowflake.py (which originally had this as a
private, dataset/warehouse-only-aware helper) so it's reusable for the
newer DDL files that need additional placeholders (@s3_bucket,
@storage_role_arn for Snowpipe) without every call site needing to know
about every possible placeholder.
"""

from __future__ import annotations


def render_sql(text: str, replacements: dict[str, str]) -> list[str]:
    """Replaces every `@placeholder` in `text` per `replacements`, then
    splits on `;` into individual statements (Snowpark's `session.sql()`
    runs one statement per call, unlike BigQuery's client.query() which
    accepts a whole script per job — see provision_bigquery.py for
    contrast). Comment-only lines are stripped; empty statements dropped.
    """
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    statements = []
    for raw_stmt in text.split(";"):
        stmt = "\n".join(line for line in raw_stmt.splitlines() if not line.strip().startswith("--")).strip()
        if stmt:
            statements.append(stmt)
    return statements
