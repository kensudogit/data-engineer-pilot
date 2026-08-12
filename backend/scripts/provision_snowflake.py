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

from src.snowflake.sql_utils import render_sql

SQL_DIR = Path(__file__).resolve().parent.parent / "src" / "snowflake"

DATABASE_DDL_FILES = ["ddl/00_database_warehouse.sql"]
TABLE_DDL_FILES = ["ddl/01_raw.sql", "ddl/02_staging.sql", "ddl/03_dwh.sql", "ddl/04_mart.sql"]
SNOWPIPE_DDL_FILES = ["ddl/01b_snowpipe.sql"]
CORTEX_ML_FILES = [
    "cortex/01_sales_forecast_model.sql",
    "cortex/02_churn_model.sql",
    "cortex/03_demand_forecast_model.sql",
]
CORTEX_SEARCH_DDL_FILES = ["cortex_search/01_documents_table.sql", "cortex_search/02_search_service.sql"]


def _run_sql_files(session, files: list[str], replacements: dict[str, str]) -> None:
    for relative_path in files:
        text = (SQL_DIR / relative_path).read_text(encoding="utf-8")
        statements = render_sql(text, replacements)
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
    parser.add_argument(
        "--apply-snowpipe-ddl",
        action="store_true",
        help="create the storage integration, external stage, and 5 auto-ingest pipes (requires --s3-bucket and --storage-role-arn; two manual AWS console steps still required after this — see ddl/01b_snowpipe.sql's header comment)",
    )
    parser.add_argument("--s3-bucket", help="S3 bucket name (no s3:// prefix), required with --apply-snowpipe-ddl")
    parser.add_argument("--storage-role-arn", help="AWS IAM role ARN for the storage integration, required with --apply-snowpipe-ddl")
    parser.add_argument(
        "--load-documents",
        action="store_true",
        help="create mart.support_documents + the Cortex Search service, and load backend/src/data/documents/*.md into it",
    )
    parser.add_argument(
        "--upload-semantic-model",
        action="store_true",
        help="create the mart.semantic_models stage and PUT the Cortex Analyst semantic_model.yaml onto it",
    )
    args = parser.parse_args()

    if not (
        args.apply_ddl
        or args.load_raw
        or args.create_models
        or args.apply_snowpipe_ddl
        or args.load_documents
        or args.upload_semantic_model
    ):
        parser.print_help()
        return
    if args.apply_snowpipe_ddl and not (args.s3_bucket and args.storage_role_arn):
        parser.error("--apply-snowpipe-ddl requires --s3-bucket and --storage-role-arn")

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

    replacements = {"@warehouse": args.warehouse, "@database": args.database}

    if args.apply_ddl:
        _run_sql_files(session, DATABASE_DDL_FILES, replacements)
        _run_sql_files(session, TABLE_DDL_FILES, replacements)
    if args.load_raw:
        load_raw(session, args.database)
    if args.apply_snowpipe_ddl:
        snowpipe_replacements = {**replacements, "@s3_bucket": args.s3_bucket, "@storage_role_arn": args.storage_role_arn}
        _run_sql_files(session, SNOWPIPE_DDL_FILES, snowpipe_replacements)
    if args.create_models:
        _run_sql_files(session, CORTEX_ML_FILES, replacements)
    if args.load_documents:
        from src.snowflake.cortex_search.load_documents import load_documents  # noqa: PLC0415

        _run_sql_files(session, CORTEX_SEARCH_DDL_FILES, replacements)
        load_documents(session, args.database)
    if args.upload_semantic_model:
        session.sql(f"CREATE STAGE IF NOT EXISTS {args.database}.mart.semantic_models").collect()
        local_path = str(SQL_DIR / "cortex_analyst" / "semantic_model.yaml")
        session.file.put(local_path, f"@{args.database}.mart.semantic_models", auto_compress=False, overwrite=True)
        print(f"uploaded semantic_model.yaml to @{args.database}.mart.semantic_models")


if __name__ == "__main__":
    main()
