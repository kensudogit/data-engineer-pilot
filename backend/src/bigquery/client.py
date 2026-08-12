from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.config import get_settings

SQL_DIR = Path(__file__).resolve().parent


class BigQueryNotConfiguredError(RuntimeError):
    """Raised when DEMO_MODE=false but BigQuery isn't actually reachable.

    Deliberately never caught to silently fall back to demo mode — a
    misconfigured "production" deployment must fail loudly at startup rather
    than quietly serve demo numbers labeled `source: "bigquery"`. See
    config.py's docstring on `demo_mode` and main.py's lifespan.
    """


@lru_cache
def get_client():
    """Returns a google.cloud.bigquery.Client. Only ever called when
    DEMO_MODE=false. Import is local to this function so the package doesn't
    need real GCP credentials just to be imported in demo mode.
    """
    from google.cloud import bigquery  # noqa: PLC0415

    settings = get_settings()
    if not settings.gcp_project_id:
        raise BigQueryNotConfiguredError("GCP_PROJECT_ID is not set but DEMO_MODE=false")
    try:
        client = bigquery.Client(project=settings.gcp_project_id)
        # Trivial round-trip to fail fast if credentials/project are actually
        # unreachable, rather than failing on the first real query later.
        list(client.query("SELECT 1").result())
    except Exception as exc:  # noqa: BLE001
        raise BigQueryNotConfiguredError(f"BigQuery is not reachable: {exc}") from exc
    return client


def run_query(sql: str) -> pd.DataFrame:
    """Runs a query against real BigQuery and returns a DataFrame. Only used
    on the DEMO_MODE=false path."""
    return get_client().query(sql).result().to_dataframe()


def load_sql(relative_path: str) -> str:
    """Reads one of the .sql files under bigquery/ddl/ or bigquery/ml/."""
    return (SQL_DIR / relative_path).read_text(encoding="utf-8")


def qualified_table(dataset: str, table: str) -> str:
    settings = get_settings()
    project = settings.gcp_project_id or "PROJECT_ID"
    return f"`{project}.{dataset}.{table}`"
