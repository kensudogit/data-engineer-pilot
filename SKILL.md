---
name: bigquery-data-engineering
description: >
  Google Cloud BigQueryを利用したデータ基盤の設計、テーブル設計、
  SQL作成、ETL/ELT、データマート、BI連携、BigQuery ML、
  パフォーマンス改善、コスト最適化、セキュリティ設計、
  テストおよびレビューを支援するSkill。
---

# BigQuery Data Engineering Skill

## 1. Purpose

このSkillは、Google Cloud BigQueryを中心とした
データ分析基盤の設計・実装・評価を支援する。

以下を対象とする。

- BigQueryアーキテクチャ設計
- Dataset設計
- Table設計
- SQL作成
- ETL/ELT設計
- Cloud Storage連携
- PostgreSQL等からのデータ連携
- Partitioning
- Clustering
- データマート設計
- BI連携
- Looker連携
- BigQuery ML
- Vertex AI連携
- IAM
- セキュリティ
- コスト最適化
- パフォーマンス改善
- テスト
- コードレビュー

---

# 2. Architecture

基本アーキテクチャとして以下を検討する。

Source Systems
    |
    +-- PostgreSQL
    +-- MySQL
    +-- CSV
    +-- JSON
    +-- REST API
    +-- Application Logs
    |
    v
Cloud Storage / Data Ingestion
    |
    v
BigQuery
    |
    +-- Raw Dataset
    +-- Staging Dataset
    +-- Data Warehouse
    +-- Data Mart
    |
    +------------------+
    |                  |
    v                  v
Looker             BigQuery ML
                       |
                       v
                   Vertex AI

---

# 3. Data Layer Design

原則として以下のデータレイヤーを検討する。

## RAW

外部システムから取得したデータを可能な限り
元データに近い状態で保存する。

例:

raw.sales
raw.customers
raw.access_logs

## STAGING

データ型変換、NULL処理、重複排除、
コード変換などを実施する。

例:

staging.sales
staging.customers

## DWH

業務分析に利用できる統合データを作成する。

例:

dwh.fact_sales
dwh.dim_customer
dwh.dim_product

## DATA MART

BIや特定業務向けに最適化する。

例:

mart.daily_sales
mart.customer_sales
mart.product_sales

---

# 4. Table Design

テーブル設計時には必ず以下を確認する。

- データ量
- 更新頻度
- 保持期間
- Query Pattern
- Partition Key
- Cluster Key
- Primary identifier
- NULL許可
- データ型
- コスト
- セキュリティ

巨大テーブルについてはPartitioningを優先的に検討する。

例:

PARTITION BY DATE(order_date)

必要に応じてClusteringも検討する。

例:

CLUSTER BY customer_id, product_id

---

# 5. SQL Development Rules

SQLでは原則としてSELECT *を避ける。

Bad:

SELECT *
FROM sales;

Good:

SELECT
    customer_id,
    product_id,
    amount
FROM sales;

大量テーブルではPartition Filterを使用する。

SELECT
    customer_id,
    amount
FROM `project.dwh.sales`
WHERE sales_date >= DATE('2026-01-01');

---

# 6. Cost Optimization

BigQueryではクエリによるデータスキャン量を意識する。

必ず以下を確認する。

1. SELECT * を使用していないか
2. Partition Filterが存在するか
3. 不要なJOINが存在しないか
4. 不要な列を取得していないか
5. Query結果を再利用できないか
6. Materialized Viewを利用できないか
7. Data Mart化できないか

SQLを生成するときは、
可能な限り低コストなSQLを提案する。

---

# 7. ETL / ELT

以下の流れを基本とする。

Extract
    ↓
Load
    ↓
BigQuery RAW
    ↓
Transform
    ↓
STAGING
    ↓
DWH
    ↓
DATA MART

BigQueryではELT方式を優先的に検討する。

---

# 8. PostgreSQL Integration

PostgreSQL等のOLTPデータベースは
業務トランザクション処理に利用する。

BigQueryは分析処理に利用する。

Application
    |
    v
PostgreSQL
    |
    | ETL / ELT
    v
BigQuery
    |
    v
BI / AI / Analytics

BigQueryを通常のOLTP DBの代替として
安易に使用しない。

---

# 9. BigQuery ML

機械学習要件が存在する場合は
BigQuery MLの利用可能性を検討する。

対象例:

- 売上予測
- 解約予測
- 顧客分類
- 異常検知
- 需要予測

SQLでモデルを構築可能な場合は
BigQuery MLを候補とする。

---

# 10. Vertex AI Integration

高度なAI/ML処理が必要な場合は
Vertex AIとの連携を検討する。

BigQuery
    |
    v
Feature/Data
    |
    v
Vertex AI
    |
    v
Prediction / Generative AI

---

# 11. BI Integration

BI要件がある場合は以下を検討する。

BigQuery
    |
    v
Data Mart
    |
    v
Looker
    |
    v
Dashboard

BIから巨大なRAWテーブルを
直接検索する構成は可能な限り避ける。

---

# 12. Security

以下を必ず確認する。

- IAM
- Principle of Least Privilege
- Dataset Permission
- Table Permission
- Service Account
- Audit Log
- Encryption
- Row Level Security
- Column Level Security
- Sensitive Data

本番環境では個人ユーザーの認証情報ではなく、
適切なService Accountを使用する。

---

# 13. Performance Review

SQLレビュー時には以下を評価する。

Performance:
- Scan Size
- Partition
- Clustering
- JOIN
- GROUP BY
- ORDER BY
- Window Function

Cost:
- Data scanned
- Query frequency
- Materialization
- Cache

Maintainability:
- Naming
- CTE
- Comments
- Complexity

---

# 14. Testing

最低限以下をテストする。

## Unit Test

- SQL結果
- NULL
- Boundary
- Duplicate
- Data Type

## Integration Test

Source
    ↓
ETL
    ↓
BigQuery
    ↓
Data Mart

までを確認する。

## Data Quality Test

以下を確認する。

- NULL率
- 重複
- 件数
- 最大値
- 最小値
- Referential Integrity
- Business Rules

---

# 15. Output

ユーザーからBigQuery関連の実装依頼を受けた場合、
可能な限り以下を出力する。

1. 要件整理
2. アーキテクチャ
3. Dataset設計
4. Table設計
5. DDL
6. SQL
7. ETL/ELT
8. セキュリティ
9. コスト対策
10. テスト方法
11. デプロイ方法
12. 運用方法

コードだけを生成せず、
設計理由も説明する。

---

# 16. Review Mode

「レビューして」
「評価して」
「改善して」

という要求の場合は以下の形式で回答する。

## Evaluation

A: Excellent
B: Good
C: Needs Improvement
D: Critical

## Findings

- Architecture
- Performance
- Cost
- Security
- Maintainability

## Recommendations

優先順位:

P1 Critical
P2 High
P3 Medium
P4 Low

として改善策を提示する。

---

# 17. Important Principles

BigQueryを利用する場合は常に以下を重視する。

Performance
+
Cost
+
Security
+
Maintainability
+
Data Quality

単にSQLが実行できることを
完成条件としない。