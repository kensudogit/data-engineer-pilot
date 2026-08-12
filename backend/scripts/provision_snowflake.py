"""CLI to provision a real Snowflake account for this pilot: create the
warehouse/database/RAW/STAGING/DWH/MART schemas, load the synthetic dataset
into RAW, apply the STAGING/DWH/MART DDL, and create the Cortex ML
Functions objects (FORECAST x2, CLASSIFICATION) — Snowpark ML's
KMeans/IsolationForest (segmentation/anomaly) are trained at FastAPI
startup instead (see src/services/segmentation_service.py and
anomaly_service.py's _prepare_snowflake), not by this script, since
Snowpark ML estimators are an in-application library, not persistent SQL
objects the way Cortex ML Functions are.

Requires real Snowflake credentials and a warehouse with Cortex enabled.
This project's own automated test suite never runs this script — it
deliberately touches a real Snowflake account, which this session had no
access to (see README.md's "重要な前提" section). Mirrors
scripts/provision_bigquery.py's CLI shape.

Usage:
    python -m scripts.provision_snowflake --account YOUR_ACCOUNT \\
        --warehouse DATA_ENGINEER_PILOT_WH --database DATA_ENGINEER_PILOT \\
        --apply-ddl --load-raw --create-models
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent.parent / "src" / "snowflake"

DATABASE_DDL_FILES = ["ddl/00_database_warehouse.sql"]
TABLE_DDL_FILES = ["ddl/01_raw.sql", "ddl/02_staging.sql", "ddl/03_dwh.sql", "ddl/04_mart.sql"]
CORTEX_ML_FILES = [
    "cortex/01_sales_forecast_model.sql",
    "cortex/02_churn_model.sql",
    "cortex/03_demand_forecast_model.sql",
]


def _render_sql(relative_path: str, warehouse: str, database: str) -> list[str]:
    text = (SQL_DIR / relative_path).read_text(encoding="utf-8")
    text = text.replace("@warehouse", warehouse).replace("@database", database)
    # Each .sql file is a semicolon-separated multi-statement script;
    # Snowpark's session.sql() runs one statement per call (unlike
    # BigQuery's client.query(), which accepts a whole script per job), so
    # split on ';' and drop empty/comment-only fragments.
    statements = []
    for raw_stmt in text.split(";"):
        stmt = "\n".join(line for line in raw_stmt.splitlines() if not line.strip().startswith("--")).strip()
        if stmt:
            statements.append(stmt)
    return statements


def _run_sql_files(session, files: list[str], warehouse: str, database: str) -> None:
    for relative_path in files:
        statements = _render_sql(relative_path, warehouse, database)
        print(f"applying {relative_path} ({len(statements)} statement(s)) ...")
        for stmt in statements:
            session.sql(stmt).collect()
        print(f"  done ({relative_path})")


def load_raw(session, database: str) -> None:
    from src.data.synth import generate_dataset

    dataset = generate_dataset(seed=42)
    tables = {
        "customers": dataset.customers,
        "subscriptions": dataset.subscriptions,
        "products": dataset.products,
        # is_injected_anomaly is generator-internal (used only by this
        # project's own pytest suite to measure detection recall) and must
        # never be loaded into a table a real anomaly-detection model trains on.
        "orders": dataset.orders.drop(columns=["is_injected_anomaly"]),
        "order_items": dataset.order_items,
    }
    for table_name, df in tables.items():
        full_name = f"{database}.raw.{table_name}"
        session.write_pandas(df, table_name.upper(), database=database, schema="RAW", auto_create_table=False, overwrite=True)
        print(f"loaded {len(df)} rows into {full_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--account", required=True, help="Snowflake account identifier")
    parser.add_argument("--warehouse", default="DATA_ENGINEER_PILOT_WH")
    parser.add_argument("--database", default="DATA_ENGINEER_PILOT")
    parser.add_argument("--apply-ddl", action="store_true", help="create warehouse/database/schemas + RAW/STAGING/DWH/MART tables")
    parser.add_argument("--load-raw", action="store_true", help="load the synthetic dataset into the RAW tables")
    parser.add_argument("--create-models", action="store_true", help="create the 3 Cortex ML Functions objects (FORECAST x2, CLASSIFICATION)")
    args = parser.parse_args()

    if not (args.apply_ddl or args.load_raw or args.create_models):
        parser.print_help()
        return

    from snowflake.snowpark import Session  # noqa: PLC0415

    session = Session.builder.configs(
        {
            "account": args.account,
            "user": os.environ["SNOWFLAKE_USER"],
            "password": os.environ["SNOWFLAKE_PASSWORD"],
            "role": os.environ.get("SNOWFLAKE_ROLE"),
            "warehouse": args.warehouse,
        }
    ).create()

    if args.apply_ddl:
        _run_sql_files(session, DATABASE_DDL_FILES, args.warehouse, args.database)
        _run_sql_files(session, TABLE_DDL_FILES, args.warehouse, args.database)
    if args.load_raw:
        load_raw(session, args.database)
    if args.create_models:
        _run_sql_files(session, CORTEX_ML_FILES, args.warehouse, args.database)


if __name__ == "__main__":
    main()
