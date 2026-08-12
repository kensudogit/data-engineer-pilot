-- PostgreSQL RAW schema — the simulated operational source system this
-- pipeline's Python ETL (backend/src/etl/run_etl.py) extracts from.
-- Run once via backend/src/etl/postgres_source.py --create-schema.

CREATE SCHEMA IF NOT EXISTS raw;
