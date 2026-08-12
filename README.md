# Data Engineer Pilot — BigQuery ML / Snowflake AI 5機能パイロット

BigQuery ML、およびSnowflake（Cortex ML Functions・Cortex LLM・Snowpark ML）を想定した5つの分析機能（売上予測・解約予測・顧客分類・異常検知・需要予測）のパイロット実装です。`SKILL.md`（BigQueryデータエンジニアリングSkill）のセクション9に明示されたユースケース全てを、1つの一貫した合成EC/SaaSデータセットの上に実装し、加えてSnowflakeを中核としたAI対応データアーキテクチャ（Cortex LLMによる自然文「AIインサイト」生成を含む）を第3の実行経路として追加しています。

## ⚠️ 重要な前提

- **GCPプロジェクト・BigQueryの実行環境、およびSnowflakeアカウントの実行環境は、いずれも未接続です。** 本リポジトリの`bigquery/ddl/*.sql`・`bigquery/ml/*.sql`・`snowflake/ddl/*.sql`・`snowflake/cortex/*.sql`・`snowflake/snowpark_ml/*.py`は、それぞれBigQuery ML／Snowflake Cortex ML Functions・Snowpark MLの公式構文に基づいて作成していますが、実環境での動作検証は行っていません。
- そのため、**デフォルトでは`EXECUTION_MODE=demo`** で動作し、各機能はBigQuery ML／Snowflakeの代わりにstatsmodels/scikit-learnによる**本物の**近似アルゴリズムを合成データに対してその場で計算します（ハードコードされた偽の数値ではありません）。全APIレスポンスの`source`フィールドで`"demo"`・`"bigquery"`・`"snowflake"`のいずれかが常に明示されます。
- 各機能の結果を要約する自然文「AIインサイト」（`ai_insight`フィールド）も同じ原則です。`EXECUTION_MODE=snowflake`時のみ実際の`SNOWFLAKE.CORTEX.COMPLETE`呼び出しで生成され（`ai_insight_generated_by: "cortex"`）、それ以外は既に計算済みの指標から組み立てたテンプレート文（`"template"`）で、生成AIが書いたかのような文言は使っていません。
- `EXECUTION_MODE=bigquery`または`EXECUTION_MODE=snowflake`で接続に失敗した場合は**起動時に失敗します**（デモ数値への静かなフォールバックはしません）。

## 1. 要件整理

- 売上予測・解約予測・顧客分類・異常検知・需要予測の5機能を、React+Next.js+TypeScriptのフロントエンドから利用できること
- 実データが存在しないため、現実的な合成データ（EC/SaaSハイブリッドドメイン）で成立させること
- 将来実GCPプロジェクトに接続すれば、そのままBigQuery MLで動作する構成にしておくこと
- Snowflakeを中核としたAI対応データアーキテクチャ（Cortex ML Functions・Cortex LLM・Snowpark ML）を第3の実行経路として追加し、将来実Snowflakeアカウントに接続すれば、コードを変えずにそのまま動作する構成にしておくこと

## 2. アーキテクチャ

```
合成データ生成器 (backend/src/data/synth.py, seed=42固定)
        |
        v
インメモリDataFrame (customers/subscriptions/products/orders/order_items)
[FastAPI起動時(lifespan)に一度だけ生成・各モデルを学習、app.stateに保持]
        |
        +---------------------+---------------------------+---------------------------+
        |                                                  |                           |
  EXECUTION_MODE=demo（既定）                    EXECUTION_MODE=bigquery      EXECUTION_MODE=snowflake
        |                                                  |                           |
  services/*.py                                   bigquery/client.py           snowflake/client.py
  statsmodels/scikit-learn で                       google-cloud-bigquery で     Cortex ML Functions
  同じインメモリデータに対し実計算                    ML.FORECAST/ML.PREDICT/       (FORECAST/CLASSIFICATION)
  + ai_insightはテンプレート文                        ML.DETECT_ANOMALIESを実行     + Snowpark ML(KMeans/
                                                                                  IsolationForest)
                                                                                + Cortex LLM COMPLETEで
                                                                                  ai_insightを実生成
        +---------------------+---------------------------+---------------------------+
                                          v
                        schemas/*.py（source: "demo"|"bigquery"|"snowflake" 必須、
                                       ai_insight/ai_insight_generated_by含む）
                                          v
                                   api/*.py（FastAPIルータ）
                                          v
                          Next.js フロントエンド（recharts, CSS Modules,
                                                  SourceBadge/AiInsightCard）
```

実運用を想定したデータフロー（`bigquery/ddl/*.sql`・`snowflake/ddl/*.sql`が対応、BigQueryはデータセット、Snowflakeはデータベース+4スキーマとして同じ4層を実装）:

```
Source Systems → Ingestion → BigQuery または Snowflake
                                                 ├─ RAW
                                                 ├─ STAGING
                                                 ├─ DWH
                                                 └─ DATA MART → BigQuery ML / Looker
                                                              → Cortex ML Functions・Snowpark ML・Cortex LLM
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

`backend/src/bigquery/ddl/`（BigQuery）と`backend/src/snowflake/ddl/`（Snowflake）の両方に、同じ RAW → STAGING → DWH → DATA MART の4層を実装しています。Snowflake版はBigQueryの「プロジェクト.データセット」構造を「データベース.スキーマ」構造に、`PARTITION BY`/`GENERATE_DATE_ARRAY`/`SAFE_DIVIDE`/`DATE_DIFF`等のBigQuery固有構文をSnowflakeの`CLUSTER BY`（今回は小規模データのため意図的に省略）/`GENERATOR`+`SEQ4`/`DIV0NULL`/`DATEDIFF`（引数順が逆転する点に注意）へ翻訳したものです。

- **RAW** (`00_datasets.sql`または`00_database_warehouse.sql`, `01_raw.sql`): 5テーブル、緩い型
- **STAGING** (`02_staging.sql`): 型変換・重複排除・NULL処理（`CREATE OR REPLACE TABLE ... AS SELECT`）
- **DWH** (`03_dwh.sql`): `dim_customer`/`dim_product`/`dim_date`/`fact_orders`/`fact_order_items`/`fact_subscription_events`。BigQuery版のfact系は`PARTITION BY <date>`＋`CLUSTER BY <頻出フィルタ列>`（スキャンバイト課金対策として直接効くため）
- **DATA MART** (`04_mart.sql`): `daily_sales`・`daily_product_demand`（売上上位20商品限定）・`customer_features`（複数スナップショット・`churned_next_30d`ラベル付き、リーク無し）・`order_transaction_features`

## 5. SQL（BigQuery ML / Snowflake Cortex ML Functions・Cortex LLM・Snowpark ML）

`backend/src/bigquery/ml/`配下、各ファイルにCREATE MODEL文＋コメントアウトされた予測取得クエリ:

| 機能 | BigQuery MLモデル | 主なOPTIONS |
|---|---|---|
| 売上予測 | ARIMA_PLUS | `time_series_id_col='channel'`, `auto_arima=TRUE`, `holiday_region='JP'` |
| 解約予測 | LOGISTIC_REG | `input_label_cols=['churned_next_30d']`, `auto_class_weights=TRUE` |
| 顧客分類 | KMEANS | `num_clusters=4`, `standardize_features=TRUE` |
| 異常検知 | AUTOENCODER | `hidden_units=[16,8,4,8,16]` + `ML.DETECT_ANOMALIES` |
| 需要予測 | ARIMA_PLUS | `time_series_id_col='product_id'`（上位20商品限定） |

`backend/src/snowflake/cortex/`（Cortex ML Functions、SQL）と`backend/src/snowflake/snowpark_ml/`（Snowpark ML、Python）に、BigQuery MLとは異なる技術で同じ5機能を実装しています:

| 機能 | Snowflake側の技術 | 備考 |
|---|---|---|
| 売上予測 | Cortex ML Functions `SNOWFLAKE.ML.FORECAST`（`SERIES_COLNAME='channel'`） | `CREATE SNOWFLAKE.ML.FORECAST <name>(...)` → `<name>!FORECAST(...)`という宣言的なオブジェクト作成＋メソッド呼び出し構文 |
| 解約予測 | Cortex ML Functions `SNOWFLAKE.ML.CLASSIFICATION` | 同上、`!PREDICT(...)`で推論 |
| 需要予測 | Cortex ML Functions `SNOWFLAKE.ML.FORECAST`（`SERIES_COLNAME='product_id'`、上位20商品限定） | 売上予測と同じ関数 |
| 顧客分類 | **Snowpark ML** `snowflake.ml.modeling.cluster.KMeans` | Cortex ML Functionsにクラスタリング用の組み込み関数が存在しないための選択 |
| 異常検知 | **Snowpark ML** `snowflake.ml.modeling.ensemble.IsolationForest` | `SNOWFLAKE.ML.ANOMALY_DETECTION`は時系列（1指標×時間軸）向けの関数であり、本プロジェクトの取引単位・多変量異常検知とは形状が合わないため不採用。BigQuery版がKMEANS距離ではなくAUTOENCODERを選んだのと同じ理由 |

さらに、**Cortex LLM Functions**（`SNOWFLAKE.CORTEX.COMPLETE`）を使い、5機能＋概要ダッシュボードそれぞれに結果を要約する自然文「AIインサイト」を生成する機能（`backend/src/snowflake/cortex/insight.py`）を追加しています。これはBigQuery MLには存在しない、Snowflake経路だけの追加機能です。

デモモードでの近似実装（`backend/src/services/*.py`）: 売上/需要予測はstatsmodels `ExponentialSmoothing`（Holt-Winters）、解約予測はscikit-learn `LogisticRegression`（ホールドアウトAUC評価）、顧客分類は`KMeans`（シルエットスコア評価）、異常検知は`IsolationForest`（合成データに混入させた既知異常に対する再現率で評価）。AIインサイトは既に計算済みの指標から組み立てたテンプレート文（`ai_insight_generated_by: "template"`）。

## 6. ETL/ELT

Extract → Load → RAW → Transform → STAGING → DWH → DATA MART（BigQuery/SnowflakeともにELT方式）。合成データをBigQueryへ投入する場合は`backend/scripts/provision_bigquery.py`、Snowflakeへ投入する場合は`backend/scripts/provision_snowflake.py`を使用します（下記デプロイ方法参照）。

## 7. セキュリティ

- 本番でBigQuery Service Accountを使う場合は必要最小限の権限（BigQuery Data Editor + Job User程度）に絞ってください
- Snowflakeでは、Cortex LLM/ML Functionsを呼び出す実行ロールに`SNOWFLAKE.CORTEX_USER`データベースロールを付与し、Cortex ML Functionsオブジェクトの作成には該当スキーマへの`CREATE SNOWFLAKE.ML.<TYPE>`権限が必要です。今回はユーザー名/パスワード認証のみに対応（本番ではキーペア/OAuth認証がSnowflake推奨）
- `GOOGLE_APPLICATION_CREDENTIALS`・`SNOWFLAKE_PASSWORD`はコミットしない（`.gitignore`で`.env`除外済み）
- 個人情報に相当するフィールドは合成データにも含めていません（顧客IDは連番、実在の氏名等は生成しません）。Cortex LLMへのプロンプトも既に計算済みの集計指標のみを渡し、生の顧客行やPIIは一切含めません

## 8. コスト対策

- 需要予測は売上上位20商品に限定（BigQuery ARIMA_PLUSは`time_series_id_col`、Snowflake ML.FORECASTは`SERIES_COLNAME`使用時、いずれも系列数に比例して学習コストが増える）
- `AUTOENCODER`の`max_iterations=20`・`hidden_units`を小さく抑制
- SQLは`SELECT *`を避け、必要な列のみを指定
- 大きなfactテーブルは全て`PARTITION BY`済みのため、実運用でのクエリはパーティションフィルタを付けること（BigQuery側のみ。Snowflakeはバイトスキャン課金ではなくウェアハウス秒課金のため、この規模のテーブルでは`CLUSTER BY`を意図的に付与していません）
- Cortex LLM COMPLETEによるAIインサイト生成はリクエスト毎ではなく`prepare()`時（起動時、ユースケースあたり1回）にのみ実行し、Cortexクレジット消費とレイテンシを抑制

## 9. テスト方法

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
pytest -v
```

49件のテストで、合成データの季節性/トレンド/異常値混入率/再現性、各サービスの精度指標（解約AUC>0.6、分類シルエット>0.3、異常検知再現率>0.15 — いずれもseed=42での実測値に基づく現実的な閾値）、APIエンドポイントの疎通と`source`フィールド、`EXECUTION_MODE=snowflake`時の未設定フェイルセーフ（`SnowflakeNotConfiguredError`）、デモモードの`ai_insight`がテンプレート生成である（`ai_insight_generated_by=="template"`）ことを検証しています。

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
4. 環境変数を切り替え: `EXECUTION_MODE=bigquery`, `GCP_PROJECT_ID=YOUR_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`
5. バックエンドを再起動（`EXECUTION_MODE=bigquery`時は起動時にBigQuery疎通確認を行い、失敗すれば起動自体が失敗します）

### 実Snowflake環境に接続する場合

1. Cortex対応リージョンのアカウント・ウェアハウスを用意し、実行ロールに`SNOWFLAKE.CORTEX_USER`データベースロールを付与
2. データベース・スキーマ作成: `backend/src/snowflake/ddl/00_database_warehouse.sql`の`@warehouse`/`@database`を実際の値に置換して実行
3. RAWデータ投入 + DDL適用 + Cortex ML Functions作成（Snowpark MLの顧客分類・異常検知は事前作成不要、起動時に都度学習）:
   ```bash
   cd backend
   python -m scripts.provision_snowflake --account YOUR_ACCOUNT --warehouse DATA_ENGINEER_PILOT_WH --database DATA_ENGINEER_PILOT --apply-ddl --load-raw --create-models
   ```
4. 環境変数を切り替え: `EXECUTION_MODE=snowflake`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`（任意で`SNOWFLAKE_ROLE`/`SNOWFLAKE_WAREHOUSE`/`SNOWFLAKE_DATABASE`/`CORTEX_MODEL`）
5. バックエンドを再起動（`EXECUTION_MODE=snowflake`時は起動時にSnowflake疎通確認を行い、失敗すれば起動自体が失敗します）

### Railway（単一サービス）

ルートの`Dockerfile`/`railway.toml`/`start.sh`で、backend(FastAPI)とfrontend(Next.js)を1コンテナ内の別プロセスとして起動します（`docker-compose.yml`によるローカル2コンテナ構成とは別経路）。Postgresは不要です（デモモードはインメモリ、実モードはBigQueryまたはSnowflake直結のため）。

## 11. 運用方法

- 合成データセットはプロセス起動時に一度だけ生成・各モデルを学習し、`app.state`に保持します。リクエスト毎の再生成・再学習は行いません
- AIインサイト（`ai_insight`）もモデルと同様に`prepare()`時に一度だけ生成し、`app.state`にキャッシュします。売上/需要予測のようにリクエスト時のhorizon_days等に依存する系列予測値そのものは、Snowflake経路では`!FORECAST()`をリクエスト都度呼び出しますが、Cortex LLM COMPLETEによるAIインサイト文はリクエスト毎に再生成しません
- ヘルスチェック: `GET /health`（`execution_mode`の現在値を含む）
- モデルの再学習が必要な場合はプロセスの再起動で対応します（このパイロットではオンライン再学習の仕組みは実装していません）

## 12. Review Mode

`SKILL.md`セクション16の形式（Evaluation A〜D、Findings、Recommendations P1〜P4）に従ったレビューをご希望の場合は「レビューして」「評価して」とお伝えください。

## 既知の制限

- BigQuery ML SQL・Snowflake SQL/Snowpark MLコードはいずれも未実行・未検証（実環境での確認は利用者側で行ってください）。特にSnowflake Cortex ML Functionsは比較的新しいAPI面のため、`CONFIG_OBJECT`等の細かい引数名は実行前に最新のSnowflake公式ドキュメントで再確認することを推奨します
- npmの依存関係（Next.jsが内部で使うpostcss/sharp）に既知の脆弱性報告がありますが、`next/image`未使用・外部CSS非使用のため実害は限定的です（Next.js 16系への破壊的アップグレードが必要なため見送り）
- デモモードのアルゴリズムはBigQuery ML/Snowflakeモデルの近似であり、同一の予測精度を保証しません
- デモモードのAIインサイトはテンプレート生成文であり、実際のCortex COMPLETEが生成した文章ではありません（`EXECUTION_MODE=snowflake`時のみ実生成）
- オンライン学習・モデルのバージョニング・Snowflake Model Registry連携は未実装です
- Snowflakeのキーペア/OAuth認証には対応していません（ユーザー名/パスワード認証のみ）
