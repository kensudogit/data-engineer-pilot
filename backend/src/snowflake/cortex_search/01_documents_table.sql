-- Support document corpus for Cortex Search. Loaded from
-- backend/src/data/documents/*.md via
-- backend/src/snowflake/cortex_search/load_documents.py
-- (backend/scripts/provision_snowflake.py --load-documents).
--
-- In a real deployment, PDFs could instead be parsed via
-- SNOWFLAKE.CORTEX.PARSE_DOCUMENT against files on a stage — this pilot
-- uses plain Markdown/text rows instead (see the plan's documented
-- decision), which is an equally valid and simpler Cortex Search corpus
-- shape; PARSE_DOCUMENT is noted here only as the realistic alternative
-- for actual PDF ingestion, not implemented in this repo.

CREATE TABLE IF NOT EXISTS @database.mart.support_documents (
  doc_id      VARCHAR PRIMARY KEY,
  title       VARCHAR NOT NULL,
  category    VARCHAR NOT NULL,  -- 'faq' | 'ops_runbook'
  content     VARCHAR NOT NULL,
  updated_at  DATE NOT NULL
);
