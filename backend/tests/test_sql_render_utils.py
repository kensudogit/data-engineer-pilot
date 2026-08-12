from __future__ import annotations

from pathlib import Path

from src.snowflake.sql_utils import render_sql

SNOWFLAKE_DIR = Path(__file__).resolve().parents[1] / "src" / "snowflake"

# Covers every placeholder used anywhere under snowflake/ddl and
# snowflake/cortex (confirmed via `grep -rho "@[a-z_0-9]*"`). Applying all
# of them to every file is harmless — replace() is a no-op for placeholders
# a given file doesn't contain.
_ALL_REPLACEMENTS = {
    "@warehouse": "DATA_ENGINEER_PILOT_WH",
    "@database": "DATA_ENGINEER_PILOT",
    "@s3_bucket": "my-test-bucket",
    "@storage_role_arn": "arn:aws:iam::123456789012:role/snowflake-role",
}


def test_render_sql_strips_comments_and_splits_statements():
    text = "-- a comment\nSELECT 1 FROM @database.raw.customers;\n-- another\nSELECT 2;"
    statements = render_sql(text, {"@database": "MYDB"})
    assert statements == ["SELECT 1 FROM MYDB.raw.customers", "SELECT 2"]


def test_render_sql_drops_empty_statements():
    text = "SELECT 1;\n\n;  \n-- only a comment\n;\nSELECT 2;"
    statements = render_sql(text, {})
    assert statements == ["SELECT 1", "SELECT 2"]


def test_every_ddl_and_cortex_sql_file_parses_to_nonempty_statements():
    """Syntax-safety-only check (no real Snowflake account this session,
    same as every other .sql file in this project) — catches the class of
    error most likely in hand-written, unexecuted SQL: a forgotten
    semicolon, an empty file, a placeholder left unreplaced in a way that
    breaks statement splitting."""
    sql_files = sorted((SNOWFLAKE_DIR / "ddl").glob("*.sql")) + sorted((SNOWFLAKE_DIR / "cortex").glob("*.sql"))
    assert len(sql_files) >= 8, "expected at least the original 4 ddl + 1 snowpipe + 3 cortex ml files"

    for path in sql_files:
        text = path.read_text(encoding="utf-8")
        statements = render_sql(text, _ALL_REPLACEMENTS)
        assert statements, f"{path} produced no statements"
        for stmt in statements:
            assert "@" not in stmt, f"{path} has an unreplaced placeholder in: {stmt[:80]}"
