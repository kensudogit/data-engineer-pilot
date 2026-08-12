"""Python ETL: extract raw.* tables from PostgreSQL, write them to a local
Parquet landing zone, and (best-effort) upload to S3.

Only the extract -> local-Parquet leg is actually exercised/verified this
session (real PostgreSQL via `docker compose up postgres`, no cloud
credentials needed). The S3 upload leg uses real, correct boto3 code but
was never run against a real bucket this session — same "written correctly,
disclosed as unverified" treatment as this project's BigQuery/Snowflake SQL.

Unlike execution_mode=bigquery/snowflake's fail-fast contract, a missing or
unreachable S3 configuration does NOT fail this script by default: it logs
and skips. This is a deliberate, different contract from the rest of the
project, not an oversight — see upload_to_s3()'s docstring for why.

Usage:
    python -m src.etl.run_etl                 # local parquet only, S3 skipped if unconfigured
    python -m src.etl.run_etl --strict-s3      # also raise if S3 is unconfigured/unreachable
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import Settings, get_settings
from src.etl.postgres_source import get_connection

logger = logging.getLogger(__name__)

TABLES = ["customers", "subscriptions", "products", "orders", "order_items"]
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "backend" / "etl_output"


def extract_table(conn, table: str) -> pd.DataFrame:
    return pd.read_sql_query(f"SELECT * FROM raw.{table}", conn)  # noqa: S608 - table name is from a fixed internal list, not user input


def write_local_parquet(df: pd.DataFrame, table: str, output_dir: Path, run_date: date) -> Path:
    """backend/etl_output/<table>/run_date=<YYYY-MM-DD>/<table>.parquet —
    Hive-style partition naming, deliberately mirroring the eventual S3 key
    layout 1:1 (see upload_to_s3) so the locally-verified path and the
    unexecuted S3/Snowpipe path share one mental model.
    """
    path = output_dir / table / f"run_date={run_date.isoformat()}" / f"{table}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", index=False)
    return path


def upload_to_s3(local_path: Path, table: str, run_date: date, settings: Settings, *, strict: bool = False) -> bool:
    """Returns True if uploaded, False if skipped.

    When `strict=False` (the default): if AWS_ACCESS_KEY_ID/
    AWS_SECRET_ACCESS_KEY/S3_BUCKET aren't all set, this logs and returns
    False rather than raising. This is a deliberately different contract
    from execution_mode=bigquery/snowflake's fail-fast rule — that rule
    exists to stop a `source: "bigquery"` API response from silently being
    demo numbers underneath. This function has no such labeling contract:
    its real, verified deliverable this session *is* the local Parquet
    file (already written by write_local_parquet before this is called),
    and S3/Snowpipe were disclosed upfront as unverified. Hard-failing an
    otherwise-correct local ETL run just because S3 env vars are unset
    would make the one fully-real piece of this pipeline artificially
    brittle for no honesty benefit.

    Pass `strict=True` (the CLI's --strict-s3 flag) once a real deployment
    is actually supposed to have S3 configured — e.g. a scheduled/CI run —
    and this raises instead of silently skipping.
    """
    configured = bool(settings.aws_access_key_id and settings.aws_secret_access_key and settings.s3_bucket)
    if not configured:
        message = "S3 upload skipped: AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY/S3_BUCKET not fully configured"
        if strict:
            raise RuntimeError(f"{message} (--strict-s3 was passed)")
        logger.info(message)
        return False

    import boto3  # noqa: PLC0415 - local import, mirrors bigquery/snowflake client local-import discipline

    client = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    key = f"{settings.s3_prefix}/{table}/run_date={run_date.isoformat()}/{table}.parquet"
    try:
        client.upload_file(str(local_path), settings.s3_bucket, key)
        logger.info("uploaded %s to s3://%s/%s", local_path, settings.s3_bucket, key)
        return True
    except Exception:  # noqa: BLE001
        if strict:
            raise
        logger.warning("S3 upload failed; local parquet at %s is unaffected", local_path, exc_info=True)
        return False


def run(output_dir: Path, run_date: date, settings: Settings, *, strict_s3: bool = False) -> list[Path]:
    conn = get_connection(settings)
    written: list[Path] = []
    try:
        for table in TABLES:
            df = extract_table(conn, table)
            path = write_local_parquet(df, table, output_dir, run_date)
            written.append(path)
            print(f"extracted {len(df)} rows from raw.{table} -> {path}")
            uploaded = upload_to_s3(path, table, run_date, settings, strict=strict_s3)
            if uploaded:
                print(f"  uploaded to s3://{settings.s3_bucket}/{settings.s3_prefix}/{table}/run_date={run_date.isoformat()}/{table}.parquet")
    finally:
        conn.close()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-date", type=date.fromisoformat, default=None)
    parser.add_argument("--strict-s3", action="store_true", help="raise instead of skipping if S3 isn't configured/reachable")
    args = parser.parse_args()

    settings = get_settings()
    run_date = args.run_date or date.today()
    run(args.output_dir, run_date, settings, strict_s3=args.strict_s3)


if __name__ == "__main__":
    main()
