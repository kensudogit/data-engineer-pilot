-- BigQuery datasets for the RAW -> STAGING -> DWH -> DATA MART layering
-- described in SKILL.md section 3. Run once per GCP project via
-- backend/scripts/provision_bigquery.py (or `bq mk --dataset`).
--
-- Replace @project with your actual GCP project id when running manually.

CREATE SCHEMA IF NOT EXISTS `@project.raw`
  OPTIONS (location = '@location');

CREATE SCHEMA IF NOT EXISTS `@project.staging`
  OPTIONS (location = '@location');

CREATE SCHEMA IF NOT EXISTS `@project.dwh`
  OPTIONS (location = '@location');

CREATE SCHEMA IF NOT EXISTS `@project.mart`
  OPTIONS (location = '@location');
