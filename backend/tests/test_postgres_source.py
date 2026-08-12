from __future__ import annotations

from src.etl.postgres_source import (
    _TABLE_COLUMNS,
    _TABLE_ORDER,
    create_schema,
    seed,
)


def test_create_schema_and_seed_row_counts_match_dataset(postgres_conn, dataset):
    """Real PostgreSQL: schema creation + seed, then row counts must match
    the synthetic dataset exactly (minus the 2 generator-internal-only
    columns, which _rows_for already drops by column selection)."""
    create_schema(postgres_conn)
    seed(postgres_conn, dataset)

    with postgres_conn.cursor() as cur:
        for table in _TABLE_ORDER:
            cur.execute(f"SELECT COUNT(*) FROM raw.{table}")
            (count,) = cur.fetchone()
            expected = len(getattr(dataset, table))
            assert count == expected, f"raw.{table}: expected {expected} rows, got {count}"


def test_seeded_orders_reference_existing_customers(postgres_conn, dataset):
    """FK integrity check on the real table — every order's customer_id
    must exist in raw.customers (this is enforced by a Postgres FK
    constraint too, so seed() would have already failed loudly if not, but
    asserting it directly documents the expectation)."""
    create_schema(postgres_conn)
    seed(postgres_conn, dataset)

    with postgres_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.orders o "
            "LEFT JOIN raw.customers c ON o.customer_id = c.customer_id "
            "WHERE c.customer_id IS NULL"
        )
        (orphans,) = cur.fetchone()
    assert orphans == 0


def test_table_columns_cover_every_ddl_column_no_more_no_less():
    """_TABLE_COLUMNS is the single source of truth for both the INSERT
    column list and which synthetic-dataset columns get dropped (e.g.
    customers.archetype, orders.is_injected_anomaly) — a typo here would
    silently corrupt every seeded row, so pin the exact expected shape."""
    assert _TABLE_COLUMNS["customers"] == [
        "customer_id", "signup_date", "churn_date", "is_active", "plan_type", "region",
    ]
    assert _TABLE_COLUMNS["orders"] == [
        "order_id", "customer_id", "order_date", "channel", "region", "order_amount", "item_count", "status",
    ]
    assert set(_TABLE_ORDER) == set(_TABLE_COLUMNS.keys())
