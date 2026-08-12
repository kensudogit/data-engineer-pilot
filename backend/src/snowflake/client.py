from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from src.config import get_settings

SQL_DIR = Path(__file__).resolve().parent


class SnowflakeNotConfiguredError(RuntimeError):
    """Raised when EXECUTION_MODE=snowflake but Snowflake isn't actually
    reachable (missing credentials, or a real connection/round-trip
    failure — including a failed SNOWFLAKE.CORTEX.COMPLETE call downstream).

    Deliberately never caught to silently fall back to demo mode — a
    misconfigured "production" deployment must fail loudly at startup
    rather than quietly serve demo numbers labeled `source: "snowflake"`.
    See config.py's docstring on `execution_mode` and main.py's lifespan —
    the identical contract already established for BigQuery in
    bigquery/client.py.
    """


@lru_cache
def get_session():
    """Returns a snowflake.snowpark.Session. Only ever called when
    EXECUTION_MODE=snowflake. Import is local to this function so the
    package doesn't need real Snowflake credentials just to be imported in
    demo mode (mirrors bigquery/client.py's local `from google.cloud import
    bigquery`).
    """
    from snowflake.snowpark import Session  # noqa: PLC0415

    settings = get_settings()
    if not (settings.snowflake_account and settings.snowflake_user and settings.snowflake_password):
        raise SnowflakeNotConfiguredError(
            "SNOWFLAKE_ACCOUNT/SNOWFLAKE_USER/SNOWFLAKE_PASSWORD are not fully set but EXECUTION_MODE=snowflake"
        )
    try:
        session = Session.builder.configs(
            {
                "account": settings.snowflake_account,
                "user": settings.snowflake_user,
                "password": settings.snowflake_password,
                "role": settings.snowflake_role,
                "warehouse": settings.snowflake_warehouse,
                "database": settings.snowflake_database,
                "schema": "MART",
            }
        ).create()
        # Trivial round-trip to fail fast if credentials/account are actually
        # unreachable, rather than failing on the first real query later.
        session.sql("SELECT 1").collect()
    except Exception as exc:  # noqa: BLE001
        raise SnowflakeNotConfiguredError(f"Snowflake is not reachable: {exc}") from exc
    return session


def load_sql(relative_path: str) -> str:
    """Reads one of the .sql files under snowflake/ddl/ or snowflake/cortex/."""
    return (SQL_DIR / relative_path).read_text(encoding="utf-8")


def qualified_table(schema: str, table: str) -> str:
    settings = get_settings()
    database = settings.snowflake_database
    return f'"{database}"."{schema}"."{table}"'
