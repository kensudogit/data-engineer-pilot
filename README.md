# Data Engineer Pilot — BigQuery ML / Snowflake AI 5機能パイロット + データパイプライン

BigQuery ML、およびSnowflake（Cortex ML Functions・Cortex LLM・Snowpark ML）を想定した5つの分析機能（売上予測・解約予測・顧客分類・異常検知・需要予測）のパイロット実装です。`SKILL.md`（BigQueryデータエンジニアリングSkill）のセクション9に明示されたユースケース全てを、1つの一貫した合成EC/SaaSデータセットの上に実装し、加えてSnowflakeを中核としたAI対応データアーキテクチャ（Cortex LLMによる自然文「AIインサイト」生成を含む）を第3の実行経路として追加しています。

これに加えて、既存5機能のデモ経路（`generate_dataset()`をインメモリで読む経路）とは**独立に並行する**、より企業データ基盤に近いデータ取り込み経路（PostgreSQL → Python ETL → Amazon S3 → Snowpipe → Snowflake RAW/STAGING/DATA MART → Power BI / Cortex Analyst / Cortex Agent → Cortex Search）を追加しています。既存5機能の動作は一切変更していません。

## ⚠️ 重要な前提

- **GCPプロジェクト・BigQueryの実行環境、およびSnowflakeアカウントの実行環境は、いずれも未接続です。** 本リポジトリの`bigquery/ddl/*.sql`・`bigquery/ml/*.sql`・`snowflake/ddl/*.sql`・`snowflake/cortex/*.sql`・`snowflake/snowpark_ml/*.py`は、それぞれBigQuery ML／Snowflake Cortex ML Functions・Snowpark MLの公式構文に基づいて作成していますが、実環境での動作検証は行っていません。
- そのため、**デフォルトでは`EXECUTION_MODE=demo`** で動作し、各機能はBigQuery ML／Snowflakeの代わりにstatsmodels/scikit-learnによる**本物の**近似アルゴリズムを合成データに対してその場で計算します（ハードコードされた偽の数値ではありません）。全APIレスポンスの`source`フィールドで`"demo"`・`"bigquery"`・`"snowflake"`のいずれかが常に明示されます。
- 各機能の結果を要約する自然文「AIインサイト」（`ai_insight`フィールド）も同じ原則です。`EXECUTION_MODE=snowflake`時のみ実際の`SNOWFLAKE.CORTEX.COMPLETE`呼び出しで生成され（`ai_insight_generated_by: "cortex"`）、それ以外は既に計算済みの指標から組み立てたテンプレート文（`"template"`）で、生成AIが書いたかのような文言は使っていません。
- **`EXECUTION_MODE=demo`（既定）でも、`OPENAI_API_KEY`を設定するとAIインサイトだけを実際のOpenAI生成文に置き換えられます**（`ai_insight_generated_by: "openai"`）。これは`source`フィールドには影響しません（ML計算はデモ経路のまま、あくまでテキスト生成だけの追加強化です）。`EXECUTION_MODE=bigquery`/`snowflake`の接続失敗とは異なり、OpenAI呼び出しの失敗はアプリを起動失敗させず、その項目だけテンプレート文にフォールバックします（詳細はセクション5・8参照）。
- `EXECUTION_MODE=bigquery`または`EXECUTION_MODE=snowflake`で接続に失敗した場合は**起動時に失敗します**（デモ数値への静かなフォールバックはしません）。
- **新規追加のデータパイプラインは、PostgreSQL → Python ETL → ローカルParquetまでを今回のセッションで実際にDockerで動作検証しています**（実測: customers 600・subscriptions 600・products 40・orders 8037・order_items 19994件）。**S3以降（S3・Snowpipe・Snowflake DDL・Cortex Search・Cortex Analyst・Cortex Agent・Power BI）は未実行・未検証**で、既存のBigQuery/Snowflake実装と同じ方針（公式構文に基づく正しいコード、実アカウントでの動作は未確認）です。詳細はセクション6・10、既知の制限を参照してください
- **Cortex Analyst・Cortex Agentには、他5機能のようなデモ／BigQuery相当の経路が一切存在しません。** `EXECUTION_MODE=snowflake`以外では、`/api/cortex-analyst/ask`・`/api/cortex-agent/ask`は常にHTTP 503（構造化JSON）を返します。フロントエンドの`/ask`ページでは、これを「Snowflake接続時のみ利用可能」という開示として表示します（本セッションでこの503→開示の動作は確認済みです）

## 1. 要件整理

- 売上予測・解約予測・顧客分類・異常検知・需要予測の5機能を、React+Next.js+TypeScriptのフロントエンドから利用できること
- 実データが存在しないため、現実的な合成データ（EC/SaaSハイブリッドドメイン）で成立させること
- 将来実GCPプロジェクトに接続すれば、そのままBigQuery MLで動作する構成にしておくこと
- Snowflakeを中核としたAI対応データアーキテクチャ（Cortex ML Functions・Cortex LLM・Snowpark ML）を第3の実行経路として追加し、将来実Snowflakeアカウントに接続すれば、コードを変えずにそのまま動作する構成にしておくこと
- 既存5機能のデモ経路を一切変更せず、より企業データ基盤に近いデータ取り込み経路（PostgreSQL → Python ETL → S3 → Snowpipe → Snowflake RAW/STAGING/MART → Power BI / Cortex Analyst / Cortex Agent → Cortex Search）を並行して追加すること。PostgreSQL/ETLは実際にDockerで動作検証すること

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

上記とは独立に並行する、より企業データ基盤に近いデータ取り込み経路（既存5機能のデモ経路には一切影響しません）:

```
PostgreSQL（Docker、実装・検証済み）
    │ python -m src.etl.postgres_source --create-schema --seed
    ▼
Python ETL（実装・検証済み）
    │ python -m src.etl.run_etl → backend/etl_output/<table>/run_date=<date>/<table>.parquet（実測）
    ▼
Amazon S3（未検証、AWS認証情報が未設定なら静かにskip・--strict-s3で例外化も可）
    ▼
Snowpipe（未実行・未検証、STORAGE INTEGRATION + 外部ステージ + AUTO_INGEST=TRUE PIPE）
    ▼
Snowflake RAW → STAGING → DATA MART
    ├──→ Power BI（connection_guide.md、.pbidsは非対応のため手動接続手順、未検証）
    ├──→ Cortex Analyst（/api/cortex-analyst/ask、自然言語→SQL、未実行・未検証）
    └──→ Cortex Agent（/api/cortex-agent/ask、未実行・未検証）
              └─ Cortex Search → 合成FAQ・運用マニュアル（backend/src/data/documents/、6文書）

Cortex Analyst・Cortex Agentはdemo/bigquery相当の経路が無く、
EXECUTION_MODE=snowflake以外では常にHTTP 503を返す
（フロントエンドの/askページで「Snowflake接続時のみ利用可能」として開示）
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

### PostgreSQL RAW（`backend/src/etl/ddl/`、実装・Docker検証済み）

上流の業務システムを模したPostgreSQL側にも、Snowflake版`01_raw.sql`と同じ5テーブル・同じ論理形状のRAWスキーマを実装しています（`00_schema.sql`でスキーマ作成、`01_raw.sql`で本体）。Snowflakeとの違いは、実在するPostgreSQLとして実務的なFK制約（`REFERENCES raw.customers(customer_id)`等）とインデックス（`idx_orders_customer_id`・`idx_orders_order_date`・`idx_order_items_order_id`・`idx_order_items_product_id`）を実際に付与している点です。`backend/src/etl/postgres_source.py`の`create_schema()`がこの2ファイルを実行してスキーマを作成します。

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

### OpenAIによるAIインサイト強化（オプション、デモ経路専用）

`OPENAI_API_KEY`を設定すると、デモ経路（`EXECUTION_MODE=demo`）のまま、AIインサイトだけを実際のOpenAI Chat Completions API（既定モデル: `gpt-4o-mini`、`OPENAI_MODEL`で変更可）による生成文に置き換えられます（`ai_insight_generated_by: "openai"`）。実装は`backend/src/ai/`配下:

- `backend/src/ai/prompts.py` — プロンプト生成関数（`build_prompt_churn`等）。Snowflake Cortex経路（`backend/src/snowflake/cortex/insight.py`）と共通利用しており、どちらの生成AIバックエンドを使うかに関わらず同じプロンプト文言を使う設計です
- `backend/src/ai/openai_client.py` — `generate_insight()`（実際のAPI呼び出し）と`enhance_with_openai()`（各serviceが呼ぶ唯一の呼び出し口。キー未設定時・API呼び出し失敗時はいずれもテンプレート文へフォールバックし、`ai_insight_generated_by`を`"template"`のまま維持）

`EXECUTION_MODE=bigquery`/`snowflake`の接続失敗とは意図的に異なる契約です。`OPENAI_API_KEY`は`source`フィールドを一切変更しません（MLの計算結果はデモ経路のまま正しく動作し続けるため）。そのためOpenAI呼び出しの失敗はアプリ全体を起動失敗させず、その項目のAIインサイトだけが静かにテンプレート文へ戻ります（ログには警告を出力）。「本物っぽく見えるが実は違う」を防ぐという同じ原則は、`ai_insight_generated_by`フィールドが常に正確であることによって別の形で担保しています。

### Cortex Search / Cortex Analyst / Cortex Agent（未実行・未検証、正しい構文）

MARTデータおよび合成FAQ・運用マニュアル文書に対する自然言語アクセスを、既存5機能とは別に追加しています。これらにはdemo/BigQuery相当の経路が一切存在しません。

- **Cortex Search**（`backend/src/snowflake/cortex_search/`）— 合成FAQ・運用マニュアル6文書（`backend/src/data/documents/*.md`、YAMLフロントマター付き）を`load_documents.py`で`mart.support_documents`へロードし、`CREATE CORTEX SEARCH SERVICE ... ON content ATTRIBUTES title, category WAREHOUSE = ... TARGET_LAG = '1 hour'`で検索サービスを作成
- **Cortex Analyst**（`backend/src/snowflake/cortex_analyst/`）— `semantic_model.yaml`（スタンドアロンYAML、テーブル/ディメンション/ファクト/verified_queries）をステージへ配置し、`POST /api/v2/cortex/analyst/message`で自然言語→SQLに対応。**新規の認証要件** — キーペア/OAuthまたはProgrammatic Access Token（PAT、`SNOWFLAKE_PAT`環境変数）が必要です（既存のSnowpark接続はユーザー名/パスワードのみのため、これは新規の未対応事項）
- **Cortex Agent**（`backend/src/snowflake/cortex_agent/`）— `POST /api/v2/cortex/agent:run`でCortex Search・Cortex Analystを横断するツール呼び出し型API。リクエストは`tools`（type/name/descriptionのみ）と`tool_resources`（名前をキーにした実設定）が分離した構造です。レスポンスは本来SSEストリーミングですが、本実装はバッファリングして単一JSONへ変換する簡略化を採用しています（本プロジェクトで構文の確信度が最も低く、実デプロイ前の再確認を推奨）
- バックエンドAPI（`backend/src/api/cortex_analyst.py`・`cortex_agent.py`）は`EXECUTION_MODE=snowflake`以外では常にHTTP 503（`{"detail": {"message": ..., "execution_mode": ...}}`）を返します。フロントエンドの`/ask`ページ（`frontend/src/app/ask/page.tsx`）はこの503を「Snowflake接続時のみ利用可能」という開示に変換して表示します

## 6. ETL/ELT

### BigQuery / Snowflake（既存、未実行・未検証）

Extract → Load → RAW → Transform → STAGING → DWH → DATA MART（BigQuery/SnowflakeともにELT方式）。合成データをBigQueryへ投入する場合は`backend/scripts/provision_bigquery.py`、Snowflakeへ投入する場合は`backend/scripts/provision_snowflake.py`を使用します（下記デプロイ方法参照）。

### PostgreSQL → Python ETL → S3（新規追加、PostgreSQL/ETLは実装・Docker検証済み）

既存5機能のデモ経路（インメモリ）とは独立した、より企業データ基盤に近い取り込み経路です。

- `backend/src/etl/postgres_source.py` — PostgreSQLへの接続・RAWスキーマ作成・合成データセット（`generate_dataset(seed=42)`と同じ生成器）の投入。CLI: `python -m src.etl.postgres_source --create-schema --seed`
- `backend/src/etl/run_etl.py` — PostgreSQLの5テーブルを`SELECT *`で抽出し、`backend/etl_output/<table>/run_date=<date>/<table>.parquet`へ書き出し（S3キー構造と1:1で対応するHive形式パーティション）。**ここまでは今回のセッションで実際にDockerで動作検証しています**（実測row数はセクション「重要な前提」参照）
- AWS認証情報（`AWS_ACCESS_KEY_ID`・`AWS_SECRET_ACCESS_KEY`・`S3_BUCKET`）が設定されていれば、同じParquetファイルをboto3で自動的にS3へアップロードします（未検証）。**未設定の場合はWARNログを出して静かにスキップします**（`--strict-s3`指定時のみ例外を送出）。これはBigQuery/Snowflake経路の「接続失敗＝起動失敗」という原則とは意図的に異なる契約です — `run_etl.py`の成果物には`source`のような「本物と誤認されうるラベル」が存在せず、ローカルParquet書き出し自体が検証対象で、S3以降は最初から未検証と明示されているため、静かなスキップの方が実用上妥当だと判断しました
- Snowflake側の取り込み（Snowpipe）についてはセクション10「Snowpipe / Cortex Search / Cortex Analyst / Cortex Agentを設定する場合」を参照

## 7. セキュリティ

- 本番でBigQuery Service Accountを使う場合は必要最小限の権限（BigQuery Data Editor + Job User程度）に絞ってください
- Snowflakeでは、Cortex LLM/ML Functionsを呼び出す実行ロールに`SNOWFLAKE.CORTEX_USER`データベースロールを付与し、Cortex ML Functionsオブジェクトの作成には該当スキーマへの`CREATE SNOWFLAKE.ML.<TYPE>`権限が必要です。今回はユーザー名/パスワード認証のみに対応（本番ではキーペア/OAuth認証がSnowflake推奨）
- `GOOGLE_APPLICATION_CREDENTIALS`・`SNOWFLAKE_PASSWORD`・`OPENAI_API_KEY`はコミットしない（`.gitignore`で`.env`除外済み）
- 個人情報に相当するフィールドは合成データにも含めていません（顧客IDは連番、実在の氏名等は生成しません）。Cortex LLM・OpenAIいずれへのプロンプトも既に計算済みの集計指標のみを渡し、生の顧客行やPIIは一切含めません
- `POSTGRES_PASSWORD`・`AWS_SECRET_ACCESS_KEY`・`SNOWFLAKE_PAT`もコミットしない（同じく`.env`除外済み）。ローカルの`docker-compose.yml`のPostgresパスワードは開発用の固定値であり、本番では使用しないでください
- S3バケットへのアクセスは必要最小限のIAM権限（対象プレフィックスへの`s3:PutObject`程度）に絞ってください。Snowpipeのストレージ統合は`STORAGE_ALLOWED_LOCATIONS`で対象プレフィックスを明示的に制限する構文にしています
- Cortex Analyst・Cortex Agentの認証はユーザー名/パスワードでは動作しません。キーペア/OAuthまたはPAT（Programmatic Access Token）が必要です — PATは有効期限付きで発行し、定期的にローテーションすることを推奨します

## 8. コスト対策

- 需要予測は売上上位20商品に限定（BigQuery ARIMA_PLUSは`time_series_id_col`、Snowflake ML.FORECASTは`SERIES_COLNAME`使用時、いずれも系列数に比例して学習コストが増える）
- `AUTOENCODER`の`max_iterations=20`・`hidden_units`を小さく抑制
- SQLは`SELECT *`を避け、必要な列のみを指定
- 大きなfactテーブルは全て`PARTITION BY`済みのため、実運用でのクエリはパーティションフィルタを付けること（BigQuery側のみ。Snowflakeはバイトスキャン課金ではなくウェアハウス秒課金のため、この規模のテーブルでは`CLUSTER BY`を意図的に付与していません）
- Cortex LLM COMPLETE・OpenAI Chat Completionsによるインサイト生成はいずれもリクエスト毎ではなく`prepare()`時（起動時）にのみ実行し、クレジット/トークン消費とレイテンシを抑制。ただし売上予測（チャネル数分）・需要予測（最大20商品分）はチャネル/商品ごとに1回ずつ呼ぶため、`OPENAI_API_KEY`設定時は起動時に合計最大27回程度のAPI呼び出しが発生する点に注意（`gpt-4o-mini`のような低コストモデルの利用を推奨）

## 9. テスト方法

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
pytest -v
```

80件のテストで、合成データの季節性/トレンド/異常値混入率/再現性、各サービスの精度指標（解約AUC>0.6、分類シルエット>0.3、異常検知再現率>0.15 — いずれもseed=42での実測値に基づく現実的な閾値）、APIエンドポイントの疎通と`source`フィールド、`EXECUTION_MODE=snowflake`時の未設定フェイルセーフ（`SnowflakeNotConfiguredError`）、デモモードの`ai_insight`がテンプレート生成である（`ai_insight_generated_by=="template"`）こと、`OPENAI_API_KEY`設定時のOpenAI生成成功パス・失敗時のテンプレートへのフォールバックパス（いずれも`unittest.mock`でOpenAI API呼び出しをモック、実際のネットワーク通信は行わない）、新規Snowflake DDL群（Snowpipe・Cortex Search・Cortex Analyst semantic model YAML）の構文安全性、合成FAQ文書コーパスの整合性、Cortex Analyst/Agent APIの503ゲート、を検証しています。

このうちPostgreSQL/ETL関連のテスト（`test_postgres_source.py`・`test_run_etl.py`の一部）は、`docker compose up postgres`でPostgreSQLコンテナが起動していれば実際のデータベースに対して実行され、起動していなければ`pytest.skip`で自動的にスキップされます（既存の「外部通信なしで全テストが通る」保証はそのまま維持）。上記80件は本セッションでPostgreSQLコンテナを起動した状態での実測値です。

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
- `docker-compose.yml`には`postgres`サービス（ホストポート5433）も定義されていますが、既存5機能のデモ経路では不要です（`backend`/`frontend`のみで動作）。PostgreSQL/ETLパイプラインを試す場合のみ`docker compose up -d postgres`で個別に起動してください

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

### PostgreSQL + Python ETLを実行する場合（実行して確認可能）

```bash
docker compose up -d postgres
cd backend
python -m src.etl.postgres_source --create-schema --seed
python -m src.etl.run_etl
```

`backend/etl_output/<table>/run_date=<date>/<table>.parquet`が5テーブル分生成されることを確認してください。AWS認証情報（`AWS_ACCESS_KEY_ID`・`AWS_SECRET_ACCESS_KEY`・`S3_BUCKET`）を設定すればS3へも自動アップロードされます（未設定ならログを出して静かにスキップ）。

### Snowpipe / Cortex Search / Cortex Analyst / Cortex Agentを設定する場合（未実行・未検証）

```bash
cd backend
# Snowpipe DDL適用（ストレージ統合・外部ステージ・PIPE）
python -m scripts.provision_snowflake --account YOUR_ACCOUNT --warehouse DATA_ENGINEER_PILOT_WH \
  --database DATA_ENGINEER_PILOT --apply-snowpipe-ddl \
  --s3-bucket YOUR_BUCKET --storage-role-arn arn:aws:iam::YOUR_ACCOUNT_ID:role/YOUR_ROLE

# Cortex Search用ドキュメントのロード
python -m scripts.provision_snowflake --account YOUR_ACCOUNT --warehouse DATA_ENGINEER_PILOT_WH \
  --database DATA_ENGINEER_PILOT --load-documents

# Cortex Analystセマンティックモデルのアップロード
python -m scripts.provision_snowflake --account YOUR_ACCOUNT --warehouse DATA_ENGINEER_PILOT_WH \
  --database DATA_ENGINEER_PILOT --upload-semantic-model
```

適用後、以下の手動作業が必要です:

1. **AWS IAM信頼ポリシー** — `DESC STORAGE INTEGRATION DATA_ENGINEER_PILOT_S3_INTEGRATION`で得た`STORAGE_AWS_IAM_USER_ARN`/`STORAGE_AWS_EXTERNAL_ID`をAWS側のIAMロールの信頼ポリシーに登録
2. **S3イベント通知** — `SHOW PIPES`で得た`notification_channel`（自動作成されたSQS ARN）をS3バケットのイベント通知（ObjectCreated）に登録。これを忘れると`AUTO_INGEST=TRUE`だけでは取り込まれません
3. **Cortex Analyst/Agentの認証** — `SNOWFLAKE_PAT`環境変数にProgrammatic Access Token（またはキーペア/OAuth）を設定。既存のユーザー名/パスワード認証では動作しません

設定後、`EXECUTION_MODE=snowflake`で起動し、フロントエンドの`/ask`ページから動作を確認してください。

### Power BIに接続する場合（未検証）

`backend/src/snowflake/powerbi/connection_guide.md`の手順（Get Data→Snowflake、手動接続）に従ってください。Snowflake向けの正式な`.pbids`プロトコル文字列は公式ドキュメントに存在しないため、本リポジトリでは`.pbids`ファイルを提供していません。

### Railway（単一サービス）

ルートの`Dockerfile`/`railway.toml`/`start.sh`で、backend(FastAPI)とfrontend(Next.js)を1コンテナ内の別プロセスとして起動します（`docker-compose.yml`によるローカル2コンテナ構成とは別経路）。Postgresは不要です（デモモードはインメモリ、実モードはBigQueryまたはSnowflake直結のため）。新規追加のPostgreSQL/ETLパイプラインはローカル検証用のコンポーネントであり、Railway本番デプロイには含まれません（`/ask`ページ・Cortex Analyst/Agent APIはRailway上でも配信されますが、`EXECUTION_MODE=demo`のままでは常に503→開示表示になります）。

## 11. 運用方法

- 合成データセットはプロセス起動時に一度だけ生成・各モデルを学習し、`app.state`に保持します。リクエスト毎の再生成・再学習は行いません
- AIインサイト（`ai_insight`）もモデルと同様に`prepare()`時に一度だけ生成し、`app.state`にキャッシュします。売上/需要予測のようにリクエスト時のhorizon_days等に依存する系列予測値そのものは、Snowflake経路では`!FORECAST()`をリクエスト都度呼び出しますが、Cortex LLM COMPLETEによるAIインサイト文はリクエスト毎に再生成しません
- ヘルスチェック: `GET /health`（`execution_mode`の現在値を含む）
- モデルの再学習が必要な場合はプロセスの再起動で対応します（このパイロットではオンライン再学習の仕組みは実装していません）
- `/api/cortex-analyst/ask`・`/api/cortex-agent/ask`は`EXECUTION_MODE`を都度チェックし、`"snowflake"`以外なら常にHTTP 503を返します（キャッシュや状態を持たないステートレスなゲート）

## 12. Review Mode

`SKILL.md`セクション16の形式（Evaluation A〜D、Findings、Recommendations P1〜P4）に従ったレビューをご希望の場合は「レビューして」「評価して」とお伝えください。

## 既知の制限

- BigQuery ML SQL・Snowflake SQL/Snowpark MLコードはいずれも未実行・未検証（実環境での確認は利用者側で行ってください）。特にSnowflake Cortex ML Functionsは比較的新しいAPI面のため、`CONFIG_OBJECT`等の細かい引数名は実行前に最新のSnowflake公式ドキュメントで再確認することを推奨します
- npmの依存関係（Next.jsが内部で使うpostcss/sharp）に既知の脆弱性報告がありますが、`next/image`未使用・外部CSS非使用のため実害は限定的です（Next.js 16系への破壊的アップグレードが必要なため見送り）
- デモモードのアルゴリズムはBigQuery ML/Snowflakeモデルの近似であり、同一の予測精度を保証しません
- デモモードのAIインサイトは既定ではテンプレート生成文であり、実際のCortex COMPLETEが生成した文章ではありません（`EXECUTION_MODE=snowflake`時のみ実生成）。ただし`OPENAI_API_KEY`を設定すれば、デモ経路のままAIインサイトだけは実際のOpenAI生成文に切り替わります — BigQuery ML/Snowflakeとは異なり、この経路は実アカウント不要で今回のセッション内でも動作検証が可能です
- オンライン学習・モデルのバージョニング・Snowflake Model Registry連携は未実装です
- 既存5機能のSnowflake経路（Cortex ML Functions/Snowpark ML/Cortex LLM COMPLETE）のSnowpark接続は、Snowflakeのキーペア/OAuth認証には対応していません（ユーザー名/パスワード認証のみ）
- 新規追加のデータパイプラインのうち、**PostgreSQL → Python ETL → ローカルParquetのみ**が実際にDockerで動作検証済みです。**S3・Snowpipe・Cortex Search・Cortex Analyst・Cortex Agent・Power BIは未実行・未検証**です（公式構文に基づき作成していますが、実AWS/Snowflakeアカウントでの動作確認は利用者側で行ってください）
- Cortex Analyst・Cortex AgentのREST APIには、既存Snowpark接続とは別の新規認証要件（キーペア/OAuthまたはPAT）があります。この認証方式は未実装です
- Cortex Agentのレスポンスは本来SSEストリーミングですが、本実装は単一JSONへバッファリングする簡略化を採用しています。忠実なストリーミング実装ではありません
- Snowpipeの手動AWSコンソール作業（IAM信頼ポリシー登録・S3イベント通知登録）は自動化していません。Snowpipe DDL適用後に手動で行う必要があります
- Power BIの`.pbids`ファイルは提供していません。Snowflake向けの正式なプロトコル文字列が公式ドキュメントに存在しないためです（`connection_guide.md`の手動接続手順を使用してください）
