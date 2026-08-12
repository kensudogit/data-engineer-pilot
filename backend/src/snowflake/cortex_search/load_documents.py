"""Parses backend/src/data/documents/*.md (YAML front matter + Markdown
body) into a DataFrame shaped for mart.support_documents, and loads it via
Snowpark's write_pandas — called from
backend/scripts/provision_snowflake.py --load-documents.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

DOCUMENTS_DIR = Path(__file__).resolve().parents[3] / "src" / "data" / "documents"


def parse_document(path: Path) -> dict:
    """Splits a file on its `---`-delimited YAML front matter and returns
    {doc_id, title, category, content, updated_at}. doc_id is the filename
    stem (stable, human-readable, matches what a real deployment would
    likely use as a natural key)."""
    text = path.read_text(encoding="utf-8")
    _, front_matter_raw, body = text.split("---", 2)
    front_matter = yaml.safe_load(front_matter_raw)
    return {
        "doc_id": path.stem,
        "title": front_matter["title"],
        "category": front_matter["category"],
        "content": body.strip(),
        "updated_at": front_matter["updated_at"],
    }


def load_all_documents(documents_dir: Path = DOCUMENTS_DIR) -> pd.DataFrame:
    docs = [parse_document(path) for path in sorted(documents_dir.glob("*.md"))]
    return pd.DataFrame(docs)


def load_documents(session, database: str) -> None:
    df = load_all_documents()
    session.write_pandas(
        df, "SUPPORT_DOCUMENTS", database=database, schema="MART", auto_create_table=False, overwrite=True
    )
    print(f"loaded {len(df)} documents into {database}.mart.support_documents")
