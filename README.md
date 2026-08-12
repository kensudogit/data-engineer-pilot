# Data Engineer Pilot — BigQuery ML 5機能パイロット

BigQuery MLを想定した5つの分析機能（売上予測・解約予測・顧客分類・異常検知・需要予測）のパイロット実装です。`SKILL.md`（BigQueryデータエンジニアリングSkill）のセクション9に明示されたユースケース全てを、1つの一貫した合成EC/SaaSデータセットの上に実装しています。

## ⚠️ 重要な前提

- **GCPプロジェクト・BigQueryの実行環境は未接続です。** 本リポジトリの`bigquery/ddl/*.sql`・`bigquery/ml/*.sql`はBigQuery MLの公式構文に基づいて作成していますが、実GCP環境での動作検証は行っていません。
- そのため、**デフォルトでは`DEMO_MODE=true`** で動作し、各機能はBigQuery MLの代わりにstatsmodels/scikit-learnによる**本物の**近似アルゴリズムを合成データに対してその場で計算します（ハードコードされた偽の数値ではありません）。全APIレスポンスの`source`フィールドで`"demo"`か`"bigquery"`かが常に明示されます。
- `DEMO_MODE=false`でBigQuery接続に失敗した場合は**起動時に失敗します**（デモ数値への静かなフォールバックはしません）。

## 1. 要件整理

- 売上予測・解約予測・顧客分類・異常検知・需要予測の5機能を、React+Next.js+TypeScriptのフロントエンドから利用できること
- 実データが存在しないため、現実的な合成データ（EC/SaaSハイブリッドドメイン）で成立させること
- 将来実GCPプロジェクトに接続すれば、そのままBigQuery MLで動作する構成にしておくこと

## 2. アーキテクチャ

```
合成データ生成器 (backend/src/data/synth.py, seed=42固定)
        |
        v
インメモリDataFrame (customers/subscriptions/products/orders/order_items)
[FastAPI起動時(lifespan)に一度だけ生成・各モデルを学習、app.stateに保持]
        |
        +--------------------------+-------------------------------+
        |                                                            |
  DEMO_MODE=true（既定）                                    DEMO_MODE=false（将来・実GCP）
        |                                                            |
  services/*.py                                             bigquery/client.py
  statsmodels/scikit-learn で                                google-cloud-bigquery で
  同じインメモリデータに対し実計算                             ML.FORECAST/ML.PREDICT/
        |                                                     ML.DETECT_ANOMALIESを実行
        +---------------------------+-------------------------------+
                                     v
                        schemas/*.py（source: "demo"|"bigquery" 必須）
                                     v
                              api/*.py（FastAPIルータ）
                                     v
                     Next.js フロントエンド（recharts, CSS Modules）
```

実運用を想定したデータフロー（`bigquery/ddl/*.sql`が対応）:

```
Source Systems → Cloud Storage / Ingestion → BigQuery
                                                 ├─ RAW
                                                 ├─ STAGING
                                                 ├─ DWH
                                                 └─ DATA MART → BigQuery ML / Looker
```

## 3. Dataset設計

合成EC/SaaSドメイン（`backend/src/data/synth.py`）:

| エンティティ | 件数目安 | 説明 |
|---|---|---|
| customers | 約600件 | 4アーキタイプ（VIP/regular/occasional/dormant_at_risk）で行動差 |
| subscriptions | 約600件 | 顧客1:1、プラン・MRR・解約日 |
| products | 40件 | カテゴリ別価格帯 |
| orders | 約6,000〜8,000件（2年分日次） | チャネル・地域・季節性・トレンド反映 |
| order_items | 約18,000〜20,000件 | 注文明細 |

決定性は`numpy.random.default_rng(42)`のみで担保（グローバル`np.random`は不使用）。トレンド（前年比+18%相当）・季節性（週末係数、12月ボーナス期、7-8月夏セール）・解約シグナル（dormant_at_risk顧客のみ、90日前からの行動変化と因果的に連動）・異常値（約1.5%の注文を3〜5倍の金額/数量で生成）を生成過程に組み込んでいます。

## 4. Table設計・DDL

`backend/src/bigquery/ddl/`配下に RAW → STAGING → DWH → DATA MART の4層で定義しています。

- **RAW** (`00_datasets.sql`, `01_raw.sql`): 5テーブル、緩い型
- **STAGING** (`02_staging.sql`): 型変換・重複排除・NULL処理（`CREATE OR REPLACE TABLE ... AS SELECT`）
- **DWH** (`03_dwh.sql`): `dim_customer`/`dim_product`/`dim_date`/`fact_orders`/`fact_order_items`/`fact_subscription_events`。fact系は`PARTITION BY <date>`＋`CLUSTER BY <頻出フィルタ列>`
- **DATA MART** (`04_mart.sql`): `daily_sales`・`daily_product_demand`（売上上位20商品限定）・`customer_features`（複数スナップショット・`churned_next_30d`ラベル付き、リーク無し）・`order_transaction_features`

## 5. SQL（BigQuery ML）

`backend/src/bigquery/ml/`配下、各ファイルにCREATE MODEL文＋コメントアウトされた予測取得クエリ:

| 機能 | モデル | 主なOPTIONS |
|---|---|---|
| 売上予測 | ARIMA_PLUS | `time_series_id_col='channel'`, `auto_arima=TRUE`, `holiday_region='JP'` |
| 解約予測 | LOGISTIC_REG | `input_label_cols=['churned_next_30d']`, `auto_class_weights=TRUE` |
| 顧客分類 | KMEANS | `num_clusters=4`, `standardize_features=TRUE` |
| 異常検知 | AUTOENCODER | `hidden_units=[16,8,4,8,16]` + `ML.DETECT_ANOMALIES` |
| 需要予測 | ARIMA_PLUS | `time_series_id_col='product_id'`（上位20商品限定） |

デモモードでの近似実装（`backend/src/services/*.py`）: 売上/需要予測はstatsmodels `ExponentialSmoothing`（Holt-Winters）、解約予測はscikit-learn `LogisticRegression`（ホールドアウトAUC評価）、顧客分類は`KMeans`（シルエットスコア評価）、異常検知は`IsolationForest`（合成データに混入させた既知異常に対する再現率で評価）。

## 6. ETL/ELT

Extract → Load → RAW → Transform → STAGING → DWH → DATA MART（BigQuery側はELT方式）。合成データをBigQueryへ投入する場合は`backend/scripts/provision_bigquery.py`を使用します（下記デプロイ方法参照）。

## 7. セキュリティ

- 本番でService Accountを使う場合は必要最小限の権限（BigQuery Data Editor + Job User程度）に絞ってください
- `GOOGLE_APPLICATION_CREDENTIALS`はコミットしない（`.gitignore`で`.env`除外済み）
- 個人情報に相当するフィールドは合成データにも含めていません（顧客IDは連番、実在の氏名等は生成しません）

## 8. コスト対策

- 需要予測は売上上位20商品に限定（`ARIMA_PLUS`は`time_series_id_col`使用時、系列数に比例して学習コストが増える）
- `AUTOENCODER`の`max_iterations=20`・`hidden_units`を小さく抑制
- SQLは`SELECT *`を避け、必要な列のみを指定
- 大きなfactテーブルは全て`PARTITION BY`済みのため、実運用でのクエリはパーティションフィルタを付けること

## 9. テスト方法

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
pytest -v
```

43件のテストで、合成データの季節性/トレンド/異常値混入率/再現性、各サービスの精度指標（解約AUC>0.6、分類シルエット>0.3、異常検知再現率>0.15 — いずれもseed=42での実測値に基づく現実的な閾値）、APIエンドポイントの疎通と`source`フィールドを検証しています。

フロントエンド:

```bash
cd frontend
npm install
npx tsc --noEmit
npm run build
```

## 10. デプロイ方法

### ローカル（Docker Compose）

```bash
docker compose up --build
```

- UI: http://localhost:3030
- API: http://localhost:8030 （Swagger: http://localhost:8030/docs）

### 実GCP環境に接続する場合

1. `gcloud auth application-default login`
2. データセット作成: `backend/src/bigquery/ddl/00_datasets.sql`の`@project`/`@location`を実際の値に置換して実行（または`bq mk --dataset`を4回）
3. RAWデータ投入 + DDL適用 + モデル作成:
   ```bash
   cd backend
   python -m scripts.provision_bigquery --project YOUR_PROJECT --location asia-northeast1 --apply-ddl --load-raw --create-models
   ```
4. 環境変数を切り替え: `DEMO_MODE=false`, `GCP_PROJECT_ID=YOUR_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`
5. バックエンドを再起動（`DEMO_MODE=false`時は起動時にBigQuery疎通確認を行い、失敗すれば起動自体が失敗します）

### Railway（単一サービス）

ルートの`Dockerfile`/`railway.toml`/`start.sh`で、backend(FastAPI)とfrontend(Next.js)を1コンテナ内の別プロセスとして起動します（`docker-compose.yml`によるローカル2コンテナ構成とは別経路）。Postgresは不要です（デモモードはインメモリ、実モードはBigQuery直結のため）。

## 11. 運用方法

- 合成データセットはプロセス起動時に一度だけ生成・各モデルを学習し、`app.state`に保持します。リクエスト毎の再生成・再学習は行いません
- ヘルスチェック: `GET /health`（`demo_mode`の現在値を含む）
- モデルの再学習が必要な場合はプロセスの再起動で対応します（このパイロットではオンライン再学習の仕組みは実装していません）

## 12. Review Mode

`SKILL.md`セクション16の形式（Evaluation A〜D、Findings、Recommendations P1〜P4）に従ったレビューをご希望の場合は「レビューして」「評価して」とお伝えください。

## 既知の制限

- BigQuery ML SQLは未実行・未検証（実GCP環境での確認は利用者側で行ってください）
- npmの依存関係（Next.jsが内部で使うpostcss/sharp）に既知の脆弱性報告がありますが、`next/image`未使用・外部CSS非使用のため実害は限定的です（Next.js 16系への破壊的アップグレードが必要なため見送り）
- デモモードのアルゴリズムはBigQuery MLモデルの近似であり、同一の予測精度を保証しません
- オンライン学習・モデルのバージョニングは未実装です
