-- Snowflake warehouse/database/schema for the RAW -> STAGING -> DWH -> DATA
-- MART layering described in SKILL.md section 3 — same 4-layer shape as
-- backend/src/bigquery/ddl/00_datasets.sql, translated to Snowflake's
-- database/schema model (Snowflake has no direct equivalent of BigQuery
-- "datasets"; one database with four schemas is the idiomatic mapping).
--
-- Replace @warehouse/@database with your actual values when running
-- manually (backend/scripts/provision_snowflake.py substitutes them).
--
-- Unquoted identifiers are case-insensitive in Snowflake (stored uppercase
-- internally) — written lowercase here purely so this file reads side by
-- side with the BigQuery DDL; it is the same object either way.

CREATE WAREHOUSE IF NOT EXISTS @warehouse
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

CREATE DATABASE IF NOT EXISTS @database;

CREATE SCHEMA IF NOT EXISTS @database.raw;
CREATE SCHEMA IF NOT EXISTS @database.staging;
CREATE SCHEMA IF NOT EXISTS @database.dwh;
CREATE SCHEMA IF NOT EXISTS @database.mart;
