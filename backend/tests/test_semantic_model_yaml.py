from __future__ import annotations

from pathlib import Path

import yaml

SEMANTIC_MODEL_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "snowflake" / "cortex_analyst" / "semantic_model.yaml"
)

_EXPECTED_TABLES = {"daily_sales", "customer_features", "daily_product_demand", "order_transaction_features"}


def _load() -> dict:
    return yaml.safe_load(SEMANTIC_MODEL_PATH.read_text(encoding="utf-8"))


def test_semantic_model_parses_as_valid_yaml():
    model = _load()
    assert isinstance(model, dict)


def test_semantic_model_has_required_top_level_keys():
    model = _load()
    assert "name" in model
    assert "description" in model
    assert "tables" in model
    assert isinstance(model["tables"], list)
    assert "verified_queries" in model
    assert isinstance(model["verified_queries"], list)


def test_semantic_model_covers_all_four_mart_tables():
    model = _load()
    table_names = {t["name"] for t in model["tables"]}
    assert table_names == _EXPECTED_TABLES


def test_every_table_has_base_table_and_at_least_one_fact_and_dimension():
    model = _load()
    for table in model["tables"]:
        assert "base_table" in table, f"{table['name']} missing base_table"
        base = table["base_table"]
        assert {"database", "schema", "table"} <= base.keys()
        assert table.get("dimensions") or table.get("time_dimensions"), f"{table['name']} has no dimensions"
        assert table.get("facts"), f"{table['name']} has no facts"


def test_every_verified_query_has_question_and_sql():
    model = _load()
    assert len(model["verified_queries"]) >= 3
    for query in model["verified_queries"]:
        assert query.get("name")
        assert query.get("question")
        assert query.get("sql")
