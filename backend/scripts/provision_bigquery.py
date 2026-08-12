"""CLI to provision a real GCP project for this pilot: create the RAW/
STAGING/DWH/MART datasets, load the synthetic dataset into RAW, apply the
STAGING/DWH/MART DDL, and create the 5 BigQuery ML models.

Requires real GCP credentials (`gcloud auth application-default login`) and
a project with BigQuery enabled. This project's own automated test suite
never runs this script — it deliberately touches real BigQuery, which this
session had no access to (see README.md's "重要な前提" section).

Usage:
    python -m scripts.provision_bigquery --project YOUR_PROJECT \\
        --location asia-northeast1 --apply-ddl --load-raw --create-models
"""

from __future__ import annotations

import argparse
from pathlib import Path

SQL_DIR = Path(__file__).resolve().parent.parent / "src" / "bigquery"

DATASET_DDL_FILES = ["ddl/00_datasets.sql"]
TABLE_DDL_FILES = ["ddl/02_staging.sql", "ddl/03_dwh.sql", "ddl/04_mart.sql"]
ML_FILES = [
    "ml/01_sales_forecast_model.sql",
    "ml/02_churn_model.sql",
    "ml/03_segmentation_model.sql",
    "ml/04_anomaly_model.sql",
    "ml/05_demand_forecast_model.sql",
]


def _render_sql(relative_path: str, project: str, location: str) -> str:
    text = (SQL_DIR / relative_path).read_text(encoding="utf-8")
    return text.replace("@project", project).replace("@location", location)


def _run_sql_files(client, files: list[str], project: str, location: str) -> None:
    for relative_path in files:
        sql = _render_sql(relative_path, project, location)
        print(f"applying {relative_path} ...")
        # BigQuery accepts a semicolon-separated multi-statement script as a
        # single query() job, which is how these .sql files are structured
        # (multiple CREATE TABLE / CREATE MODEL statements per file).
        job = client.query(sql, location=location)
        job.result()
        print(f"  done ({relative_path})")


def load_raw(client, project: str) -> None:
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
        table_id = f"{project}.raw.{table_name}"
        job = client.load_table_from_dataframe(df, table_id)
        job.result()
        print(f"loaded {len(df)} rows into {table_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True, help="GCP project id")
    parser.add_argument("--location", default="asia-northeast1")
    parser.add_argument("--apply-ddl", action="store_true", help="create datasets + RAW/STAGING/DWH/MART tables")
    parser.add_argument("--load-raw", action="store_true", help="load the synthetic dataset into the RAW tables")
    parser.add_argument("--create-models", action="store_true", help="run the 5 CREATE MODEL statements")
    args = parser.parse_args()

    if not (args.apply_ddl or args.load_raw or args.create_models):
        parser.print_help()
        return

    from google.cloud import bigquery  # noqa: PLC0415

    client = bigquery.Client(project=args.project)

    if args.apply_ddl:
        _run_sql_files(client, DATASET_DDL_FILES, args.project, args.location)
        _run_sql_files(client, ["ddl/01_raw.sql", *TABLE_DDL_FILES], args.project, args.location)
    if args.load_raw:
        load_raw(client, args.project)
    if args.create_models:
        _run_sql_files(client, ML_FILES, args.project, args.location)


if __name__ == "__main__":
    main()
