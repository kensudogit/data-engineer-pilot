from __future__ import annotations

import pytest

from src.data.synth import SyntheticDataset, generate_dataset

SEED = 42


@pytest.fixture(scope="session")
def dataset() -> SyntheticDataset:
    """Session-scoped: generation + downstream model training is nontrivial
    work (~a few seconds total across all 5 services), and every test in
    this suite operates on the same seed=42 dataset anyway."""
    return generate_dataset(seed=SEED)


@pytest.fixture(scope="session")
def postgres_conn():
    """Real PostgreSQL connection for the ETL pipeline's integration tests
    (test_postgres_source.py, test_run_etl.py). Unlike
    test_snowflake_client.py's pattern (which *forces* an unconfigured
    state and asserts failure), this fixture *wants* a real connection and
    skips cleanly when one isn't available — so this project's existing
    "56 tests run with zero external dependencies" guarantee stays intact
    by default, while still giving real coverage whenever
    `docker compose up postgres` is running.
    """
    from src.etl.postgres_source import PostgresConnectionError, get_connection

    try:
        conn = get_connection()
    except PostgresConnectionError:
        pytest.skip("PostgreSQL not reachable; run `docker compose up postgres` to enable this test")
    yield conn
    conn.close()
