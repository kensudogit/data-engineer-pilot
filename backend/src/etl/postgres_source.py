"""PostgreSQL "operational source system" — the thing this pipeline's
Python ETL (backend/src/etl/run_etl.py) extracts from. This is a real,
locally-Docker-verified layer (unlike everything from S3 onward in this
pipeline), simulating an upstream application database that a real company
would already have, separate from any analytics warehouse.

Never called from FastAPI's lifespan (backend/src/main.py) — the existing
demo/bigquery/snowflake execution paths keep reading generate_dataset()
directly in-process, completely unaffected by whether Postgres exists or is
reachable. This module is a standalone CLI + pytest fixture helper only.

Usage:
    python -m src.etl.postgres_source --create-schema --seed
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.config import Settings, get_settings
from src.data.synth import SyntheticDataset, generate_dataset

logger = logging.getLogger(__name__)

DDL_DIR = Path(__file__).resolve().parent / "ddl"

# Column order matches ddl/01_raw.sql exactly. Selecting only these columns
# is also how the two generator-internal-only columns (customers.archetype,
# orders.is_injected_anomaly — see data/synth.py) get dropped before they
# ever reach a table meant to represent a real operational system, mirroring
# the same precedent already established in
# backend/scripts/provision_snowflake.py's load_raw().
_TABLE_COLUMNS: dict[str, list[str]] = {
    "customers": ["customer_id", "signup_date", "churn_date", "is_active", "plan_type", "region"],
    "products": ["product_id", "name", "category", "unit_price", "launch_date"],
    "subscriptions": ["subscription_id", "customer_id", "plan", "mrr", "start_date", "end_date", "status"],
    "orders": ["order_id", "customer_id", "order_date", "channel", "region", "order_amount", "item_count", "status"],
    "order_items": ["order_item_id", "order_id", "product_id", "quantity", "unit_price", "discount_pct"],
}

# FK-safe load order: customers/products have no FK deps, subscriptions/
# orders depend on customers, order_items depends on orders+products.
_TABLE_ORDER = ["customers", "products", "subscriptions", "orders", "order_items"]


class PostgresConnectionError(RuntimeError):
    """Raised when PostgreSQL isn't reachable. Only ever raised by this
    standalone ETL CLI / test-fixture helper — never by FastAPI's lifespan,
    so it can never affect the demo/bigquery/snowflake execution paths."""


def get_connection(settings: Settings | None = None):
    """Returns a psycopg2 connection. Local import so the package need not
    be importable unless this module is actually used (mirrors
    bigquery/client.py's and snowflake/client.py's local-import discipline
    for optional external dependencies)."""
    import psycopg2  # noqa: PLC0415

    settings = settings or get_settings()
    try:
        return psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            connect_timeout=5,
        )
    except Exception as exc:  # noqa: BLE001
        raise PostgresConnectionError(
            f"PostgreSQL is not reachable at {settings.postgres_host}:{settings.postgres_port} "
            f"(db={settings.postgres_db}) — run `docker compose up postgres` first: {exc}"
        ) from exc


def create_schema(conn) -> None:
    for filename in ("00_schema.sql", "01_raw.sql"):
        sql = (DDL_DIR / filename).read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
    conn.commit()


def _rows_for(dataset: SyntheticDataset, table: str) -> list[tuple]:
    df = getattr(dataset, table)[_TABLE_COLUMNS[table]].astype(object)
    df = df.where(df.notnull(), None)
    return list(df.itertuples(index=False, name=None))


def seed(conn, dataset: SyntheticDataset) -> None:
    from psycopg2.extras import execute_values  # noqa: PLC0415

    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE {', '.join(f'raw.{t}' for t in _TABLE_ORDER)} CASCADE")
        for table in _TABLE_ORDER:
            rows = _rows_for(dataset, table)
            if not rows:
                continue
            columns = ", ".join(_TABLE_COLUMNS[table])
            execute_values(cur, f"INSERT INTO raw.{table} ({columns}) VALUES %s", rows)
            logger.info("loaded %d rows into raw.%s", len(rows), table)
    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--create-schema", action="store_true", help="create the raw schema + 5 tables")
    parser.add_argument("--seed", action="store_true", help="load the synthetic dataset into raw.*")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--db")
    parser.add_argument("--user")
    parser.add_argument("--password")
    args = parser.parse_args()

    if not (args.create_schema or args.seed):
        parser.print_help()
        return

    overrides = {
        k: v
        for k, v in {
            "postgres_host": args.host,
            "postgres_port": args.port,
            "postgres_db": args.db,
            "postgres_user": args.user,
            "postgres_password": args.password,
        }.items()
        if v is not None
    }
    settings = get_settings().model_copy(update=overrides)

    conn = get_connection(settings)
    try:
        if args.create_schema:
            create_schema(conn)
            print("schema created (raw.customers/subscriptions/products/orders/order_items)")
        if args.seed:
            dataset = generate_dataset(seed=settings.synth_seed)
            seed(conn, dataset)
            print("seed complete")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
