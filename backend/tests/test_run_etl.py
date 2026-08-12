from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from src.config import get_settings
from src.etl.postgres_source import create_schema, seed
from src.etl.run_etl import TABLES, extract_table, upload_to_s3, write_local_parquet


def _fake_settings(**overrides):
    return get_settings().model_copy(update=overrides)


def test_extract_and_write_local_parquet_round_trips(postgres_conn, dataset, tmp_path):
    """Real PostgreSQL + real local Parquet write — the one part of this
    whole pipeline actually exercised end-to-end this session."""
    create_schema(postgres_conn)
    seed(postgres_conn, dataset)

    run_date = date(2026, 1, 1)
    for table in TABLES:
        df = extract_table(postgres_conn, table)
        assert len(df) == len(getattr(dataset, table))

        path = write_local_parquet(df, table, tmp_path, run_date)
        assert path.exists()
        assert path == tmp_path / table / f"run_date={run_date.isoformat()}" / f"{table}.parquet"

        round_tripped = pd.read_parquet(path)
        assert len(round_tripped) == len(df)
        assert list(round_tripped.columns) == list(df.columns)


def test_upload_to_s3_skips_when_unconfigured():
    settings = _fake_settings(aws_access_key_id=None, aws_secret_access_key=None, s3_bucket=None)
    uploaded = upload_to_s3(
        local_path=Path("dummy.parquet"),
        table="customers",
        run_date=date(2026, 1, 1),
        settings=settings,
        strict=False,
    )
    assert uploaded is False


def test_upload_to_s3_raises_when_unconfigured_and_strict():
    settings = _fake_settings(aws_access_key_id=None, aws_secret_access_key=None, s3_bucket=None)
    try:
        upload_to_s3(
            local_path=Path("dummy.parquet"),
            table="customers",
            run_date=date(2026, 1, 1),
            settings=settings,
            strict=True,
        )
        raise AssertionError("expected RuntimeError")
    except RuntimeError:
        pass


def test_upload_to_s3_calls_boto3_with_expected_bucket_and_key(tmp_path):
    settings = _fake_settings(
        aws_access_key_id="AKIAFAKE", aws_secret_access_key="secret", aws_region="ap-northeast-1",
        s3_bucket="my-bucket", s3_prefix="raw",
    )
    local_file = tmp_path / "customers.parquet"
    local_file.write_bytes(b"fake parquet content")

    fake_client = MagicMock()
    with patch("boto3.client", return_value=fake_client) as mock_boto_client:
        uploaded = upload_to_s3(local_file, "customers", date(2026, 1, 1), settings, strict=False)

    assert uploaded is True
    mock_boto_client.assert_called_once_with(
        "s3", region_name="ap-northeast-1", aws_access_key_id="AKIAFAKE", aws_secret_access_key="secret"
    )
    fake_client.upload_file.assert_called_once_with(
        str(local_file), "my-bucket", "raw/customers/run_date=2026-01-01/customers.parquet"
    )


def test_upload_to_s3_failure_is_swallowed_when_not_strict(tmp_path):
    settings = _fake_settings(
        aws_access_key_id="AKIAFAKE", aws_secret_access_key="secret", s3_bucket="my-bucket",
    )
    local_file = tmp_path / "customers.parquet"
    local_file.write_bytes(b"fake parquet content")

    fake_client = MagicMock()
    fake_client.upload_file.side_effect = RuntimeError("network error")
    with patch("boto3.client", return_value=fake_client):
        uploaded = upload_to_s3(local_file, "customers", date(2026, 1, 1), settings, strict=False)

    assert uploaded is False  # never raises when not strict, local parquet already safe on disk
