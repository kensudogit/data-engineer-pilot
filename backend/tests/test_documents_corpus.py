from __future__ import annotations

import datetime

from src.snowflake.cortex_search.load_documents import DOCUMENTS_DIR, load_all_documents, parse_document

_ALLOWED_CATEGORIES = {"faq", "ops_runbook"}


def test_corpus_has_expected_number_of_documents():
    md_files = sorted(DOCUMENTS_DIR.glob("*.md"))
    assert len(md_files) == 6


def test_every_document_has_required_front_matter_and_nonempty_body():
    for path in sorted(DOCUMENTS_DIR.glob("*.md")):
        doc = parse_document(path)
        assert doc["doc_id"] == path.stem
        assert doc["title"], f"{path} has empty title"
        assert doc["category"] in _ALLOWED_CATEGORIES, f"{path} has unexpected category: {doc['category']}"
        assert len(doc["content"]) > 100, f"{path} body looks too short"
        assert isinstance(doc["updated_at"], datetime.date)


def test_load_all_documents_returns_one_row_per_file_with_unique_doc_ids():
    df = load_all_documents()
    assert len(df) == 6
    assert df["doc_id"].is_unique
    assert set(df.columns) == {"doc_id", "title", "category", "content", "updated_at"}


def test_corpus_covers_both_faq_and_all_five_ops_runbooks():
    df = load_all_documents()
    assert (df["category"] == "faq").sum() == 1
    ops_docs = df[df["category"] == "ops_runbook"]
    assert len(ops_docs) == 5
    expected_ids = {"ops_sales_forecast", "ops_churn", "ops_segmentation", "ops_anomaly", "ops_demand_forecast"}
    assert set(ops_docs["doc_id"]) == expected_ids
