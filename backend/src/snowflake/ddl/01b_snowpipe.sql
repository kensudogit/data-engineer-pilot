-- Snowpipe auto-ingest from S3 — the link between backend/src/etl/run_etl.py's
-- S3 upload leg (unverified this session, see run_etl.py's docstring) and
-- Snowflake's raw.* tables (backend/src/snowflake/ddl/01_raw.sql).
--
-- Uses the storage-integration + IAM-role approach (the current recommended
-- pattern), not the older raw-SQS-ARN style. This file only covers the SQL
-- side; TWO MANUAL AWS-CONSOLE STEPS are required outside this repo before
-- ingestion actually works (documented in full in README.md's デプロイ方法
-- section — do not skip either one):
--
--   1. After running this file, `DESC STORAGE INTEGRATION @database_s3_integration`
--      returns STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID — register
--      both in the trust policy of the AWS IAM role named by @storage_role_arn,
--      so Snowflake's system account is allowed to assume it.
--   2. After creating the pipes below, `SHOW PIPES LIKE '%_pipe'` (or
--      `DESC PIPE <name>`) returns a `notification_channel` — an
--      auto-provisioned SQS queue ARN. Register THAT ARN as the S3 bucket's
--      event notification target (ObjectCreated / PUT events) in the AWS
--      console. AUTO_INGEST=TRUE alone does nothing without this — it's what
--      actually triggers Snowpipe when a new file lands in the bucket.
--
-- Never executed against a real AWS/Snowflake account this session — same
-- "correct syntax, undeployed" disclosure as the rest of this project's
-- BigQuery/Snowflake SQL. Re-verify exact clause names against current
-- Snowflake docs before a real deployment.

CREATE STORAGE INTEGRATION IF NOT EXISTS @database_s3_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '@storage_role_arn'
  STORAGE_ALLOWED_LOCATIONS = ('s3://@s3_bucket/raw/');

CREATE STAGE IF NOT EXISTS @database.raw.s3_landing_zone
  URL = 's3://@s3_bucket/raw/'
  STORAGE_INTEGRATION = @database_s3_integration
  FILE_FORMAT = (TYPE = PARQUET);

-- One pipe per RAW table. Each expects Parquet files under
-- s3://<bucket>/raw/<table>/run_date=<date>/<table>.parquet — the exact
-- layout backend/src/etl/run_etl.py's write_local_parquet()/upload_to_s3()
-- already produce, so the S3 key structure and this COPY INTO's expected
-- prefix are deliberately kept in lockstep.

CREATE PIPE IF NOT EXISTS @database.raw.customers_pipe
  AUTO_INGEST = TRUE
  AS
  COPY INTO @database.raw.customers
  FROM @database.raw.s3_landing_zone/customers/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

CREATE PIPE IF NOT EXISTS @database.raw.subscriptions_pipe
  AUTO_INGEST = TRUE
  AS
  COPY INTO @database.raw.subscriptions
  FROM @database.raw.s3_landing_zone/subscriptions/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

CREATE PIPE IF NOT EXISTS @database.raw.products_pipe
  AUTO_INGEST = TRUE
  AS
  COPY INTO @database.raw.products
  FROM @database.raw.s3_landing_zone/products/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

CREATE PIPE IF NOT EXISTS @database.raw.orders_pipe
  AUTO_INGEST = TRUE
  AS
  COPY INTO @database.raw.orders
  FROM @database.raw.s3_landing_zone/orders/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

CREATE PIPE IF NOT EXISTS @database.raw.order_items_pipe
  AUTO_INGEST = TRUE
  AS
  COPY INTO @database.raw.order_items
  FROM @database.raw.s3_landing_zone/order_items/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
