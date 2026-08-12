-- Cortex Search over mart.support_documents — the corpus Cortex Agent's
-- cortex_search tool (backend/src/snowflake/cortex_agent/agent_config.py)
-- queries. Never executed against a real account this session; re-verify
-- clause names against current Snowflake docs before a real deployment.

CREATE OR REPLACE CORTEX SEARCH SERVICE @database.mart.support_search
  ON content
  ATTRIBUTES title, category
  WAREHOUSE = @warehouse
  TARGET_LAG = '1 hour'
  AS
  SELECT doc_id, title, category, content, updated_at
  FROM @database.mart.support_documents;
