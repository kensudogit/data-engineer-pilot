"use client";

/**
 * 画面右下のドラッグ可能な利用手順パネル（localStorage で位置・開閉を保存）。
 * Data Engineer Pilot — アーキテクチャ・demo/bigquery/snowflakeの3経路・
 * 5機能の使い方・AIインサイト（Cortex LLM生成）を表示。
 * デザインは Scraping Platform / Ecosystem Platform の UsageGuidePanel と共通（CSS はそのまま流用）。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import styles from "./UsageGuidePanel.module.css";

const STORAGE_KEY = "data-engineer-pilot-usage-guide-v1";
const PANEL_WIDTH = 440;

type GuideStep = {
  title: string;
  body: string;
  items?: readonly string[];
};

type FeaturedBlock = {
  badge: string;
  title: string;
  body: string;
  items?: readonly string[];
  variant?:
    | "architecture"
    | "rag"
    | "image"
    | "embed"
    | "guard"
    | "prompt"
    | "eval"
    | "agent"
    | "deploy"
    | "pipeline"
    | "cortex";
};

const valueFeatured: FeaturedBlock = {
  badge: "Value",
  title: "本ツールの位置づけ",
  body:
    "BigQuery ML / Snowflake（Cortex ML Functions・Cortex LLM・Snowpark ML）を想定した5つの分析ユースケース（売上予測・解約予測・顧客分類・異常検知・需要予測）を、1つの一貫した合成EC/SaaSデータセットの上で一気通貫に確認できるパイロットです。GCP・Snowflakeいずれも未接続の現状でも、statsmodels/scikit-learnによる本物の近似計算で「同じ画面・同じAPI形状のまま」機能を検証でき、実環境に接続すればコードを変えずにBigQuery MLまたはSnowflakeへ切り替えられます。",
  variant: "agent",
  items: [
    "未接続でも検証可能 — EXECUTION_MODE=demo（既定）なら合成データに対しローカルで本物のML計算を実行、ハードコードされた偽の数値ではない",
    "本番切り替えはコード変更なし — 環境変数 EXECUTION_MODE=bigquery|snowflake + 各認証情報を渡すだけで切り替わる設計",
    "混同防止 — 全APIレスポンスに source: \"demo\"|\"bigquery\"|\"snowflake\" が必須で入り、画面上にも常にバッジで明示される",
    "AIインサイトも同じ原則 — Snowflake経路は実際のCortex COMPLETE生成文（ai_insight_generated_by:\"cortex\"）、OPENAI_API_KEY設定時はデモ経路のままOpenAI生成文（\"openai\"）、それ以外はテンプレート生成文（\"template\"）と明示的にタグ分けする",
    "OpenAIはデモ経路への追加強化 — OPENAI_API_KEY設定はsourceフィールドを変えない（MLの計算自体はデモ経路のまま）。API呼び出しが失敗してもアプリは起動失敗せず、その項目だけテンプレート文に静かにフォールバックする（BigQuery/Snowflakeの接続失敗とは異なる契約）",
    "フェイルセーフ — bigquery/snowflake経路で接続に失敗した場合はデモ数値へ静かにフォールバックせず、起動自体を失敗させる",
  ],
};

const architectureFeatured: FeaturedBlock = {
  badge: "Architecture",
  title: "Next.js BFF + FastAPI + BigQuery ML / Snowflake（3経路）",
  body:
    "ブラウザは常に同一オリジン（または localhost:3030）のみを見ます。Next.js の rewrites が /api・/health・/docs を同一オリジン経由で FastAPI :8000 へプロキシします。FastAPI起動時（lifespan）に合成データセットを一度だけ生成し、5つのモデルを一度だけ学習してapp.stateに保持するため、リクエスト毎の再学習は発生しません。",
  variant: "architecture",
  items: [
    "Next.js — / (概要) · /sales-forecast · /churn · /segmentation · /anomaly · /demand-forecast",
    "FastAPI :8000 — /api/overview 他5エンドポイント・Swagger",
    "demo経路 — statsmodels(ExponentialSmoothing) / scikit-learn(LogisticRegression・KMeans・IsolationForest) を合成データに対しその場で計算",
    "bigquery経路 — google-cloud-bigquery 経由で ARIMA_PLUS / LOGISTIC_REG / KMEANS / AUTOENCODER の CREATE MODEL + ML.FORECAST/ML.PREDICT/ML.DETECT_ANOMALIES を実行",
    "snowflake経路 — Cortex ML Functions（SNOWFLAKE.ML.FORECAST/CLASSIFICATION）・Snowpark ML（KMeans/IsolationForest）・Cortex LLM（SNOWFLAKE.CORTEX.COMPLETE、AIインサイト生成）を実行",
    "Health — GET /health（execution_modeの現在値を含む、frontend経由でも到達可）",
    "Swagger — http://localhost:8030/docs",
  ],
};

const snowflakeFeatured: FeaturedBlock = {
  badge: "Snowflake",
  title: "Snowflake経路（Cortex ML Functions・Cortex LLM・Snowpark ML）",
  body:
    "BigQueryとは独立した第3の実行経路として、Snowflakeを中核としたAI対応アーキテクチャを追加しています。技術ごとの役割分担が明確に分かれているのが特徴です。",
  variant: "image",
  items: [
    "Cortex ML Functions（コード不要のSQLネイティブ古典ML）— 売上予測・需要予測はSNOWFLAKE.ML.FORECAST、解約予測はSNOWFLAKE.ML.CLASSIFICATION",
    "Snowpark ML（Python、Cortexとは別のライブラリ）— 顧客分類はKMeans、異常検知はIsolationForest。クラスタリングや多変量取引異常検知にはCortex ML Functionsの組み込み関数が存在しないための選択（BigQuery版がKMEANS距離ではなくAUTOENCODERを選んだのと同じ理由）",
    "Cortex LLM Functions（生成AI）— SNOWFLAKE.CORTEX.COMPLETEで各ユースケースの結果を要約する自然文「AIインサイト」を生成し、各機能ページに表示",
    "provision_snowflake.py — DDL適用・データ投入・Cortex ML Functionsオブジェクト作成をBigQuery版provision_bigquery.pyと同じCLI構造で提供（未実行・未検証）",
  ],
};

const postgresEtlFeatured: FeaturedBlock = {
  badge: "ETL",
  title: "PostgreSQL → Python ETL（実装・Docker検証済み）",
  body:
    "デモ経路（generate_dataset()をインメモリで読む既存5機能）とは別の、並行するデータ取り込み経路です。上流の業務システムを模したPostgreSQLコンテナに合成データを実際に投入し、Pythonで抽出してローカルParquetへ書き出すところまでを、今回のセッションで実際にDockerで動作確認しています。本プロジェクトで初めて「クラウド接続を要さずに実データフローがend-to-endで検証できた」区間です。",
  variant: "pipeline",
  items: [
    "起動 — docker compose up -d postgres（ホストポート5433、他案件の5432と衝突回避）",
    "スキーマ作成・シード — python -m src.etl.postgres_source --create-schema --seed（RAW 5テーブル、FK制約・インデックス付き）",
    "ETL実行 — python -m src.etl.run_etl（実測: customers 600・subscriptions 600・products 40・orders 8037・order_items 19994件を抽出）",
    "出力 — backend/etl_output/<table>/run_date=<date>/<table>.parquet（S3キー構造と1:1で対応するHive形式パーティション）",
    "S3アップロードは条件付き — AWS認証情報が未設定ならWARNログを出して静かにスキップ（--strict-s3指定時のみ例外）。BigQuery/Snowflake経路の「fail loudly」原則とは意図的に異なる契約 — ローカルParquet書き出し自体が本区間の検証対象で、S3以降は最初から未検証と明示されているため",
    "テスト — pytest（実PostgreSQL接続時のみ実行、docker compose up postgresが未起動ならpytest.skipで自動スキップし既存の「外部依存なしで全テストが通る」保証を維持）",
  ],
};

const cortexPipelineFeatured: FeaturedBlock = {
  badge: "Pipeline",
  title: "S3 → Snowpipe → MART → Power BI / Cortex Analyst / Cortex Agent（未実行・未検証）",
  body:
    "PostgreSQL/ETLより先の区間は、これまでのBigQuery/Snowflake実装と同じ方針で用意しています — 公式ドキュメントの構文に基づく正しいコード・SQL・設定ですが、実際のAWS/Snowflakeアカウントに対しては今回のセッションでは未実行・未検証です。",
  variant: "cortex",
  items: [
    "Snowpipe — STORAGE INTEGRATION（IAMロールベース）+ 外部ステージ + AUTO_INGEST=TRUE のPIPE。デプロイ後に手動AWS作業が2つ必要（① DESC STORAGE INTEGRATIONで得たIAM ARN/External IDをAWS側の信頼ポリシーに登録、② SHOW PIPESで得たSQS ARNをS3イベント通知に登録 — これを忘れるとAUTO_INGEST=TRUEだけでは何も起きない）",
    "Cortex Search — 合成FAQ・運用マニュアル6文書（backend/src/data/documents/）をmart.support_documentsへロードし、CORTEX SEARCH SERVICEを作成",
    "Cortex Analyst — MARTスキーマ4テーブルのセマンティックモデル（YAML）をステージへ配置し自然言語→SQLに対応。新規の認証要件 — キーペア/OAuthまたはProgrammatic Access Token（PAT）が必要（既存のSnowpark接続はユーザー名/パスワードのみのため、これは新規の未対応事項）",
    "Cortex Agent — Cortex Search（文書検索）とCortex Analyst（MART検索）を横断するツール呼び出し型API。レスポンスは本来SSEストリーミングだが、本実装ではバッファリングして単一JSONとして返す簡略化を採用（構文の確信度も本プロジェクトで最も低く、要再確認）",
    "Power BI — Snowflake向けの正式な.pbidsプロトコル文字列は公式ドキュメントに存在しないため使用せず、手動接続手順（connection_guide.md）+ 実在するPower Query M関数Snowflake.Databases()のスニペットを提供",
    "APIゲート — /api/cortex-analyst/ask・/api/cortex-agent/askはEXECUTION_MODE=snowflake以外では常にHTTP 503（構造化JSON）を返す。この2機能にはデモ/BigQuery相当の経路が一切存在しないため、200+フラグではなく503でサービス未提供を表現",
    "画面 — /ask（AIに質問する）で確認可能。EXECUTION_MODE=demo（既定）では「Snowflake接続時のみ利用可能」の開示のみが表示される（本セッションで確認済み）",
  ],
};

const salesFeatured: FeaturedBlock = {
  badge: "1",
  title: "売上予測（/sales-forecast）",
  body:
    "チャネル別（オンライン/店舗等）の日次売上を、過去実績から将来へ延長予測します。BigQuery MLでは ARIMA_PLUS（time_series_id_col='channel', auto_arima=TRUE, holiday_region='JP'）、Snowflakeでは Cortex ML Functions の SNOWFLAKE.ML.FORECAST（SERIES_COLNAME='channel'）、デモ経路では statsmodels の Holt-Winters（ExponentialSmoothing）を各チャネルごとに学習します。",
  variant: "rag",
  items: [
    "チャネル選択 — プルダウンで対象チャネルを切り替え",
    "予測期間 — horizon_days（既定30日）をドロップダウンで変更可能",
    "グラフ — 実績（history）と予測（forecast）を1本の線で連続表示、予測区間はp10〜p90の80%信頼区間帯（Area）",
    "精度指標 — ホールドアウト（直近14日）でのMAE・RMSEを画面上部に表示",
    "AIインサイト — 結果を要約する自然文をタグ付きで表示（既定はテンプレート生成、OPENAI_API_KEY設定時はOpenAI生成、Snowflake接続時はCortex COMPLETE生成）",
  ],
};

const churnFeatured: FeaturedBlock = {
  badge: "2",
  title: "解約予測（/churn）",
  body:
    "各顧客の今後30日以内の解約確率をスコアリングします。BigQuery MLでは LOGISTIC_REG（input_label_cols=['churned_next_30d'], auto_class_weights=TRUE）、Snowflakeでは Cortex ML Functions の SNOWFLAKE.ML.CLASSIFICATION、デモ経路では scikit-learn の LogisticRegression（class_weight='balanced'）を使用。ラベルはリーク無しの時点指定特徴量（point-in-time features）から学習しています。",
  variant: "guard",
  items: [
    "リスクフィルタ — min_risk（低・中・高）で絞り込み可能",
    "件数 — limit で表示件数を調整",
    "テーブル — 顧客ID・解約確率・リスク帯（high/medium/low）・プラン種別・地域・在籍日数を一覧表示",
    "精度指標 — ホールドアウトAUC（seed=42実測で約0.69）を画面上部に表示",
    "AIインサイト — 結果を要約する自然文をタグ付きで表示（既定はテンプレート生成、OPENAI_API_KEY設定時はOpenAI生成、Snowflake接続時はCortex COMPLETE生成）",
  ],
};

const segmentationFeatured: FeaturedBlock = {
  badge: "3",
  title: "顧客分類（/segmentation）",
  body:
    "RFM（Recency/Frequency/Monetary）指標をもとに顧客を4クラスタへ分類します。BigQuery MLでは KMEANS（num_clusters=4, standardize_features=TRUE）、Snowflakeでは Cortex ML Functionsにクラスタリング用の組み込み関数がないため Snowpark ML の KMeans、デモ経路では StandardScaler + KMeans(4) を使用。クラスタは平均購買額の高い順に「VIP → 優良顧客 → 一般顧客 → 休眠リスク」と一意にラベル付けされます（3経路とも同じランク方式ラベリングを使用）。",
  variant: "embed",
  items: [
    "散布図 — 横軸recency_days・縦軸monetary_90d、バブルサイズがfrequency_90d（recharts ScatterChart + ZAxis）",
    "クラスタサマリ — 各クラスタのラベル・件数・平均購買額をカード表示",
    "精度指標 — シルエットスコア（seed=42実測で約0.46）を画面上部に表示",
    "顧客テーブル — 各顧客がどのクラスタに属するかを一覧で確認可能",
    "AIインサイト — 結果を要約する自然文をタグ付きで表示（既定はテンプレート生成、OPENAI_API_KEY設定時はOpenAI生成、Snowflake接続時はCortex COMPLETE生成）",
  ],
};

const anomalyFeatured: FeaturedBlock = {
  badge: "4",
  title: "異常検知（/anomaly）",
  body:
    "注文（取引）単位で金額・数量の異常を検知します。BigQuery MLでは AUTOENCODER（hidden_units=[16,8,4,8,16]）+ ML.DETECT_ANOMALIES、Snowflakeでは（時系列向けのSNOWFLAKE.ML.ANOMALY_DETECTIONは本用途に不適合のため）Snowpark ML の IsolationForest、デモ経路では scikit-learn の IsolationForest（contamination=0.015）を使用。合成データ生成時に約1.5%の注文へ意図的に3〜5倍の金額/数量異常を混入させており、その再現率をpytestで測定しています。",
  variant: "prompt",
  items: [
    "期間フィルタ — window_days で直近N日分に絞り込み",
    "件数 — limit で表示件数を調整",
    "散布図 — 通常（グレー）と異常検知（赤）を色分け表示",
    "精度指標 — 異常スコアのcontamination設定と、混入させた既知異常に対する再現率（seed=42実測で約0.29、無作為検知の約1.5%と比べ約10〜20倍）を画面上部に表示",
    "AIインサイト — 結果を要約する自然文をタグ付きで表示（既定はテンプレート生成、OPENAI_API_KEY設定時はOpenAI生成、Snowflake接続時はCortex COMPLETE生成）",
  ],
};

const demandFeatured: FeaturedBlock = {
  badge: "5",
  title: "需要予測（/demand-forecast）",
  body:
    "商品別の日次販売数量を将来へ延長予測します。BigQuery MLでは ARIMA_PLUS（time_series_id_col='product_id'）、Snowflakeでは Cortex ML Functions の SNOWFLAKE.ML.FORECAST（SERIES_COLNAME='product_id'）、デモ経路では statsmodels の Holt-Winters を商品ごとに学習。コスト対策として売上上位20商品に限定しています（time_series_id_col/SERIES_COLNAME使用時、系列数に比例して学習コストが増えるため）。",
  variant: "eval",
  items: [
    "商品選択 — プルダウンで対象商品（上位20商品）を切り替え",
    "予測期間 — horizon_days（既定30日）をドロップダウンで変更可能",
    "グラフ — 売上予測と同じComposedChartパターン（実績・予測・p10/p90信頼区間帯）",
    "除外ルール — 履歴データ点数が一定未満の商品は学習対象から自動的に除外（MIN_HISTORY_POINTS）",
    "AIインサイト — 結果を要約する自然文をタグ付きで表示（既定はテンプレート生成、OPENAI_API_KEY設定時はOpenAI生成、Snowflake接続時はCortex COMPLETE生成）",
  ],
};

const deployFeatured: FeaturedBlock = {
  badge: "Deploy",
  title: "Docker Compose / ローカル開発",
  body:
    "backend / frontend の2コンテナ構成です（PostgreSQL不要 — デモ経路はインメモリ、実経路はBigQueryまたはSnowflake直結のため）。ローカルポートは他案件との衝突を避けるため8030/3030を使用しています。",
  variant: "deploy",
  items: [
    "Compose — docker compose up --build → UI :3030 / API :8030",
    "Backend 単体 — cd backend && uvicorn src.main:app --reload --port 8000（要 Python 3.12venv）",
    "Frontend 単体 — cd frontend && npm run dev",
    "テスト — cd backend && pytest（合成データに対して56件のテストを実行、外部通信・GCP/Snowflake/OpenAI接続なし、いずれもモック検証）",
    "Health — /health（execution_modeを含む）· Swagger UI で API 確認",
  ],
};

const techStack = [
  "Python 3.12 · FastAPI",
  "BigQuery ML（ARIMA_PLUS/LOGISTIC_REG/KMEANS/AUTOENCODER）",
  "Snowflake Cortex ML Functions（FORECAST/CLASSIFICATION）",
  "Snowpark ML（KMeans/IsolationForest）",
  "Snowflake Cortex LLM（COMPLETE、AIインサイト生成）",
  "OpenAI Chat Completions（gpt-4o-mini、デモ経路のAIインサイト強化・オプション）",
  "statsmodels · scikit-learn（demo経路）",
  "pandas · numpy（合成データ生成、seed固定）",
  "Next.js 15 · React 19",
  "TypeScript · CSS Modules · recharts",
  "google-cloud-bigquery / snowflake-snowpark-python（実経路）",
  "PostgreSQL 16（Docker、実装・検証済み）",
  "psycopg2 / boto3（ETL → S3、実装・検証済み〜未検証）",
  "Snowpipe（STORAGE INTEGRATION、未実行・未検証）",
  "Cortex Search / Cortex Analyst / Cortex Agent（未実行・未検証）",
  "Power BI（Power Query M、未検証）",
  "Docker Compose",
] as const;

const archDiagram = `Browser (Analyst)
    │ HTTPS
    ▼
Next.js :3030 (local) / :3000 (container)
    ├─ / /sales-forecast /churn /segmentation /anomaly /demand-forecast
    └─ /api/* · /health · /docs
              │ rewrite / proxy
              ▼
         FastAPI :8000  (lifespanで合成データ生成+5モデル学習を一度だけ実行)
              ├─ EXECUTION_MODE=demo（既定）
              │     └─ services/*.py — statsmodels / scikit-learn で実計算
              │        + AIインサイトはテンプレート生成文
              ├─ EXECUTION_MODE=bigquery（実GCP接続時）
              │     └─ bigquery/client.py — BigQuery ML (CREATE MODEL / ML.FORECAST /
              │                              ML.PREDICT / ML.DETECT_ANOMALIES)
              └─ EXECUTION_MODE=snowflake（実Snowflake接続時）
                    └─ snowflake/client.py — Cortex ML Functions (FORECAST/CLASSIFICATION)
                       + Snowpark ML (KMeans/IsolationForest)
                       + Cortex LLM COMPLETE でAIインサイトを実生成
              全レスポンス共通: source: "demo" | "bigquery" | "snowflake"

並行するデータ取り込み経路（既存5機能のデモ経路とは独立、追加のみ）:
PostgreSQL（Docker, 実装・検証済み）
    │ python -m src.etl.postgres_source --create-schema --seed
    ▼
Python ETL（実装・検証済み）
    │ python -m src.etl.run_etl → backend/etl_output/*.parquet（実測）
    ▼
Amazon S3（未検証、認証情報なければ静かにskip）
    ▼
Snowpipe（未実行・未検証、STORAGE INTEGRATION + AUTO_INGEST）
    ▼
Snowflake RAW → STAGING → DATA MART
    ├──→ Power BI（connection_guide.md、未検証）
    ├──→ Cortex Analyst（/api/cortex-analyst/ask、未実行・未検証）
    └──→ Cortex Agent（/api/cortex-agent/ask、未実行・未検証）
              └─ Cortex Search → PDF/FAQ/文書（合成6文書）
   Cortex Analyst/Agentは demo/bigquery相当の経路が無く、
   EXECUTION_MODE=snowflake以外では常にHTTP 503を返す（/askで確認可）`;

type GuideSection = {
  label: string;
  steps: readonly GuideStep[];
};

const guideSections: readonly GuideSection[] = [
  {
    label: "クイックスタート",
    steps: [
      {
        title: "パネル操作・画面遷移",
        body: "本パネルは全画面で表示されます。PC ではヘッダーをドラッグして位置を変更でき、▼▲ で折りたたみ可能です。",
        items: [
          "PC — ヘッダーをドラッグで移動 · ▼▲ で開閉 · 位置はブラウザに自動保存",
          "ナビ — 概要 · 売上予測 · 解約予測 · 顧客分類 · 異常検知 · 需要予測 · AIに質問する",
          "推奨フロー — 概要でサマリ確認 → 各機能ページで詳細・グラフを確認",
        ],
      },
      {
        title: "起動と接続確認（最初に）",
        body: "デモ前にフロント・API が生きていること、デモモードで動作していることを確認します。",
        items: [
          "Compose — docker compose up --build",
          "UI — http://localhost:3030",
          "API — http://localhost:8030/docs",
          "Health — http://localhost:8030/health（execution_mode:\"demo\"であることを確認、または同一オリジン /health）",
        ],
      },
    ],
  },
  {
    label: "5機能の使い方",
    steps: [
      salesFeatured,
      churnFeatured,
      segmentationFeatured,
      anomalyFeatured,
      demandFeatured,
    ].map((f) => ({ title: `${f.badge}. ${f.title}`, body: f.body, items: f.items })),
  },
  {
    label: "概要ダッシュボード（/）",
    steps: [
      {
        title: "全機能サマリ",
        body: "5機能それぞれの主要指標（累計売上・解約AUC・分類シルエットスコア・異常検知再現率・需要予測対象商品数など）を1画面でまとめて確認できます。",
        items: [
          "カード — 各カードをクリックすると該当機能の詳細画面へ遷移",
          "総顧客数・アクティブ顧客数・累計注文数・累計売上を画面上部に表示",
          "sourceバッジ — デモモード・実BigQuery ML・実Snowflakeのいずれで動作しているかを常に明示",
          "AIインサイト — 各機能ページ上部にCortex/OpenAI/テンプレート生成いずれかの要約文をタグ付きで表示",
        ],
      },
    ],
  },
  {
    label: "実GCP環境への接続方法",
    steps: [
      {
        title: "① GCPプロジェクトの準備",
        body: "実際のBigQuery MLで動かす場合の手順です（このパイロット自体では未実施・未検証）。",
        items: [
          "gcloud auth application-default login で認証",
          "backend/src/bigquery/ddl/00_datasets.sql の @project・@location を実値に置換して実行（RAW/STAGING/DWH/MARTの4データセットを作成）",
        ],
      },
      {
        title: "② データ投入・DDL適用・モデル作成",
        body: "backend/scripts/provision_bigquery.py で一括実行できます。",
        items: [
          "cd backend && python -m scripts.provision_bigquery --project YOUR_PROJECT --location asia-northeast1 --apply-ddl --load-raw --create-models",
          "合成データセット（このパイロットと同じseed=42生成）がRAWテーブルへロードされ、STAGING/DWH/MARTのDDLと5つのCREATE MODEL文が適用される",
        ],
      },
      {
        title: "③ 環境変数の切り替え",
        body: "EXECUTION_MODE=bigquery にすると起動時にBigQuery疎通確認を行います。",
        items: [
          "EXECUTION_MODE=bigquery / GCP_PROJECT_ID=YOUR_PROJECT / GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json",
          "接続に失敗した場合は起動自体が失敗します（デモ数値への静かなフォールバックはしない設計）",
          "成功すればAPIレスポンスのsourceが\"bigquery\"に切り替わり、画面上のバッジも連動して変わる",
        ],
      },
    ],
  },
  {
    label: "実Snowflake環境への接続方法",
    steps: [
      {
        title: "① データベース・ウェアハウスの準備",
        body: "実際のSnowflakeで動かす場合の手順です（このパイロット自体では未実施・未検証）。Cortexが有効なアカウント・ウェアハウスが必要です。",
        items: [
          "SNOWFLAKE.CORTEX_USERデータベースロールを実行ロールに付与（Cortex LLM/ML Functions利用に必須）",
          "backend/src/snowflake/ddl/00_database_warehouse.sql の @warehouse・@database を実値に置換して実行（ウェアハウス+RAW/STAGING/DWH/MARTの4スキーマを作成）",
        ],
      },
      {
        title: "② データ投入・DDL適用・Cortex ML Functions作成",
        body: "backend/scripts/provision_snowflake.py で一括実行できます。Snowpark ML（顧客分類・異常検知）はCortex ML Functionsと異なり事前作成不要 — FastAPI起動時に都度学習されます。",
        items: [
          "cd backend && python -m scripts.provision_snowflake --account YOUR_ACCOUNT --warehouse DATA_ENGINEER_PILOT_WH --database DATA_ENGINEER_PILOT --apply-ddl --load-raw --create-models",
          "合成データセット（このパイロットと同じseed=42生成）がRAWテーブルへロードされ、STAGING/DWH/MARTのDDLとCortex ML Functions（FORECAST×2・CLASSIFICATION）が作成される",
        ],
      },
      {
        title: "③ 環境変数の切り替え",
        body: "EXECUTION_MODE=snowflake にすると起動時にSnowflake疎通確認を行います。",
        items: [
          "EXECUTION_MODE=snowflake / SNOWFLAKE_ACCOUNT・SNOWFLAKE_USER・SNOWFLAKE_PASSWORD / 任意でSNOWFLAKE_ROLE・SNOWFLAKE_WAREHOUSE・SNOWFLAKE_DATABASE・CORTEX_MODEL",
          "接続に失敗した場合は起動自体が失敗します（デモ数値への静かなフォールバックはしない設計、BigQuery経路と同じ契約）",
          "成功すればAPIレスポンスのsourceが\"snowflake\"に切り替わり、ai_insightもCortex COMPLETEによる実生成文（ai_insight_generated_by:\"cortex\"）に変わる",
        ],
      },
    ],
  },
  {
    label: "データパイプライン拡張（PostgreSQL→ETL→S3→Snowpipe→MART→BI/AI）",
    steps: [
      {
        title: "① PostgreSQL + ETL（実行して確認可能）",
        body: "既存5機能のデモ経路とは独立した、並行するデータ取り込み経路です。ここまでは今回のセッションで実際にDockerで動作検証しています。",
        items: [
          "docker compose up -d postgres（ホストポート5433）",
          "cd backend && python -m src.etl.postgres_source --create-schema --seed",
          "python -m src.etl.run_etl → backend/etl_output/<table>/run_date=<date>/<table>.parquet が生成されることを確認",
          "AWS認証情報（AWS_ACCESS_KEY_ID等）を設定すればS3へも自動アップロード、未設定ならWARNログを出して静かにスキップ（--strict-s3で例外化も可能）",
        ],
      },
      {
        title: "② Snowpipe（未実行・未検証、正しい構文）",
        body: "backend/src/snowflake/ddl/01b_snowpipe.sqlをSnowflake側で適用した後、2つの手動AWS作業が必要です。",
        items: [
          "python -m scripts.provision_snowflake --apply-snowpipe-ddl --s3-bucket YOUR_BUCKET --storage-role-arn arn:aws:iam::...:role/...",
          "① DESC STORAGE INTEGRATIONで得たSTORAGE_AWS_IAM_USER_ARN/STORAGE_AWS_EXTERNAL_IDをAWS側IAMロールの信頼ポリシーに登録",
          "② SHOW PIPESで得たnotification_channel（自動作成されたSQS ARN）をS3バケットのイベント通知（ObjectCreated）に登録 — これを忘れるとAUTO_INGEST=TRUEだけでは取り込まれない",
        ],
      },
      {
        title: "③ Cortex Search / Cortex Analyst / Cortex Agent（未実行・未検証、正しい構文）",
        body: "MARTデータと合成FAQ・運用マニュアル文書に対するAI機能です。demo/bigquery相当の経路は存在しません。",
        items: [
          "python -m scripts.provision_snowflake --load-documents（合成6文書をmart.support_documentsへロードしCORTEX SEARCH SERVICEを作成）",
          "python -m scripts.provision_snowflake --upload-semantic-model（semantic_model.yamlをステージへ配置）",
          "認証 — Cortex Analyst/AgentのREST APIはキーペア/OAuthまたはPAT（Programmatic Access Token）が必要（SNOWFLAKE_PAT環境変数）。既存のSnowpark接続（ユーザー名/パスワード）とは別の認証経路",
          "確認 — フロントエンドの /ask ページから質問。EXECUTION_MODE=snowflake以外では常に503を返し「Snowflake接続時のみ利用可能」と表示される（本セッションで確認済みの唯一の実挙動）",
        ],
      },
      {
        title: "④ Power BI（実在する手順のみ使用）",
        body: "Snowflake向けの正式な.pbidsプロトコル文字列は存在しないため、手動接続手順を使用します。",
        items: [
          "backend/src/snowflake/powerbi/connection_guide.md — Get Data→Snowflakeの手動接続手順 + Power Query M関数 Snowflake.Databases() のスニペット",
          "backend/src/snowflake/powerbi/semantic_model_notes.md — テーブル関連・DAXメジャー例",
        ],
      },
    ],
  },
  {
    label: "ローカル開発・運用",
    steps: [
      {
        title: "Docker Compose（推奨）",
        body: "backend / frontend の 2 サービス構成です（Postgres不要）。",
        items: [
          "前提 — Docker Desktop",
          "docker compose up --build",
          "UI :3030 · API :8030 · Health /health",
          "停止 — docker compose down",
        ],
      },
      {
        title: "Backend / Frontend 単体起動",
        body: "IDE 開発時はサービスを分けて起動できます。",
        items: [
          "Backend — cd backend && uvicorn src.main:app --reload --port 8000（Python 3.12推奨、gcc/gfortran要— statsmodels/scipyのビルドに必要な場合あり）",
          "テスト — cd backend && pytest -v（56件、合成データに対し外部通信なしで実行）",
          "Frontend — cd frontend && npm install && npm run dev",
          "型チェック/ビルド確認 — npx tsc --noEmit && npm run build",
        ],
      },
      {
        title: "前提・制限（必ず読む）",
        body: "本パイロットの現時点のスコープ外事項です。",
        items: [
          "BigQuery ML SQL・Snowflake SQL/Snowpark MLコードは未実行・未検証 — 公式構文に基づき作成していますが、実環境での動作確認は利用者側で行ってください",
          "デモ経路の数値は近似 — statsmodels/scikit-learnによる本物の計算ですが、BigQuery MLやSnowflakeモデルと同一の予測精度を保証しません",
          "デモ経路のAIインサイトは既定ではテンプレート生成 — 実際のCortex COMPLETE呼び出しはEXECUTION_MODE=snowflake時のみだが、OPENAI_API_KEYを設定すればデモ経路のままOpenAI生成に切り替えられる（唯一、実アカウント不要でこのセッション内でも動作検証できる経路）",
          "オンライン学習・モデルのバージョニング・Snowflake Model Registry連携は未実装 — 再学習が必要な場合はプロセスの再起動で対応",
          "需要予測は売上上位20商品に限定 — コスト対策のため（time_series_id_col/SERIES_COLNAME使用時、系列数に比例して学習コストが増加）",
          "合成データはseed=42で完全に決定的 — 実データではないため、数値そのものに業務的な意味はない",
          "S3・Snowpipe・Cortex Search・Cortex Analyst・Cortex Agent・Power BIは未実行・未検証 — 公式構文に基づき作成していますが、実AWS/Snowflakeアカウントでの動作確認は利用者側で行ってください。実行検証済みなのはPostgreSQL→Python ETL→ローカルParquetの区間のみです",
          "Cortex Analyst/Agentは新規の認証要件（キーペア/OAuthまたはPAT）が必要 — 既存のSnowpark接続（ユーザー名/パスワード）だけでは動作しません",
          "Cortex AgentのレスポンスはSSEストリーミングが正式仕様ですが、本実装は単一JSONへバッファリングする簡略化を採用しています（忠実なストリーミング実装ではありません）",
        ],
      },
      {
        title: "よくあるエラーと対処",
        body: "画面や数値が期待どおりでないときの確認手順です。",
        items: [
          "画面に「デモモード」バッジしか出ない — EXECUTION_MODE=demoが既定のため正常動作。実BigQuery ML/Snowflakeを見たい場合は上記の接続方法を実施",
          "/health が404・接続エラー — バックエンドコンテナが起動しているか docker compose ps / docker logs dep-backend で確認",
          "特定の商品/チャネルが選択肢に出ない — 需要予測は売上上位20商品限定、履歴データ点数が少なすぎる系列はMIN_HISTORY_POINTSにより自動除外",
          "起動が失敗する（EXECUTION_MODE=bigquery/snowflake時）— 接続失敗による意図的な起動失敗です。認証情報・プロジェクトID(またはアカウント)・権限を確認",
          "pytestの精度系テストが失敗する — seed=42での実測値を基準にした閾値のため、合成データ生成ロジックを変更した場合は再学習後の実測値に合わせて閾値を見直してください",
          "PostgreSQL関連テストが自動でスキップされる — docker compose up postgresが未起動の場合の正常動作（pytest.skip）。実行するにはPostgreSQLコンテナを起動してから再度pytestを実行",
          "/ask で常に「Snowflake接続時のみ利用可能」と表示される — EXECUTION_MODE=demoが既定のため正常動作。Cortex Analyst/Agentにはデモ相当の経路が存在しないため、これは他5機能と異なりバグではない",
        ],
      },
    ],
  },
];

const L = {
  title: "利用手順",
  subtitle: "Architecture & Ops",
  dragHint: "ドラッグで移動",
  expand: "開く",
  collapse: "閉じる",
  heroTitle: "Data Engineer Pilot 基盤",
  heroLead:
    "BigQuery ML / Snowflake（Cortex ML Functions・Cortex LLM・Snowpark ML）想定の5機能（売上予測・解約予測・顧客分類・異常検知・需要予測）を、1つの合成EC/SaaSデータセットの上でdemo/bigquery/snowflakeの3経路から確認できるパイロット基盤です。未接続でも本物の近似計算で機能検証が完結します。",
  stackLabel: "Tech stack",
  diagramLabel: "Service topology",
  workflowLabel: "詳細利用手順",
  scrollHint: "↓ 5機能それぞれの使い方・実GCP/Snowflakeへの接続方法・運用手順は下へ",
  footer:
    "▼▲ で開閉 · PC はヘッダーをドラッグして移動 · スマホは画面下部のボトムシート · 表示状態は自動保存されます。全ての数値は合成データ（seed=42）に基づくデモです。",
} as const;

type SavedState = {
  x: number;
  y: number;
  expanded: boolean;
};

function defaultPosition(mobile = false) {
  if (typeof window === "undefined") return { x: 24, y: 24 };
  if (mobile || window.innerWidth < 768) {
    return { x: 8, y: Math.max(72, window.innerHeight - 72) };
  }
  const x = Math.max(16, window.innerWidth - PANEL_WIDTH - 24);
  const y = Math.max(72, window.innerHeight - 520);
  return { x, y };
}

function clampPosition(x: number, y: number, width: number, height: number) {
  const maxX = Math.max(8, window.innerWidth - width - 8);
  const maxY = Math.max(8, window.innerHeight - height - 8);
  return {
    x: Math.min(Math.max(8, x), maxX),
    y: Math.min(Math.max(8, y), maxY),
  };
}

const variantClass: Record<NonNullable<FeaturedBlock["variant"]>, string> = {
  architecture: styles.featuredArchitecture,
  rag: styles.featuredRag,
  image: styles.featuredImage,
  embed: styles.featuredEmbed,
  guard: styles.featuredGuard,
  prompt: styles.featuredPrompt,
  eval: styles.featuredEval,
  agent: styles.featuredAgent,
  deploy: styles.featuredDeploy,
  pipeline: styles.featuredPipeline,
  cortex: styles.featuredCortex,
};

function FeaturedSection({ block }: { block: FeaturedBlock }) {
  const variant = block.variant ?? "architecture";
  return (
    <section className={`${styles.featured} ${variantClass[variant]}`} aria-label={block.title}>
      <div className={styles.featuredHead}>
        <span className={styles.featuredBadge}>{block.badge}</span>
        <strong>{block.title}</strong>
      </div>
      <p>{block.body}</p>
      {block.items?.length ? (
        <ul className={styles.items}>
          {block.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

export function UsageGuidePanel() {
  const panelRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);

  const [ready, setReady] = useState(false);
  const [expanded, setExpanded] = useState(true);
  const [pos, setPos] = useState({ x: 24, y: 24 });
  const [dragging, setDragging] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mobile = window.innerWidth < 768;
    setIsMobile(mobile);
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as SavedState;
        setPos(mobile ? defaultPosition(true) : { x: parsed.x, y: parsed.y });
        setExpanded(mobile ? false : parsed.expanded);
      } catch {
        setPos(defaultPosition(mobile));
        if (mobile) setExpanded(false);
      }
    } else {
      setPos(defaultPosition(mobile));
      if (mobile) setExpanded(false);
    }
    setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    const payload: SavedState = { ...pos, expanded };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  }, [pos, expanded, ready]);

  useEffect(() => {
    if (!ready) return;
    const onResize = () => {
      const mobile = window.innerWidth < 768;
      setIsMobile(mobile);
      if (mobile) return;
      const el = panelRef.current;
      if (!el) return;
      setPos((current) => clampPosition(current.x, current.y, el.offsetWidth, el.offsetHeight));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [ready]);

  const onHeaderPointerDown = useCallback(
    (e: React.PointerEvent<HTMLElement>) => {
      if (isMobile) return;
      if ((e.target as HTMLElement).closest("button")) return;
      dragRef.current = {
        pointerId: e.pointerId,
        startX: e.clientX,
        startY: e.clientY,
        originX: pos.x,
        originY: pos.y,
      };
      setDragging(true);
      e.currentTarget.setPointerCapture(e.pointerId);
    },
    [pos.x, pos.y, isMobile],
  );

  const onHeaderPointerMove = useCallback((e: React.PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    const el = panelRef.current;
    const width = el?.offsetWidth ?? PANEL_WIDTH;
    const height = el?.offsetHeight ?? 120;
    setPos(
      clampPosition(drag.originX + (e.clientX - drag.startX), drag.originY + (e.clientY - drag.startY), width, height),
    );
  }, []);

  const onHeaderPointerUp = useCallback((e: React.PointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== e.pointerId) return;
    dragRef.current = null;
    setDragging(false);
    e.currentTarget.releasePointerCapture(e.pointerId);
  }, []);

  if (!ready) return null;

  return (
    <div
      ref={panelRef}
      className={[styles.panel, expanded ? styles.expanded : styles.collapsed, dragging ? styles.dragging : ""]
        .filter(Boolean)
        .join(" ")}
      style={isMobile ? undefined : { left: pos.x, top: pos.y, width: PANEL_WIDTH }}
      role="dialog"
      aria-label={L.title}
      aria-modal="false"
    >
      <header
        className={styles.header}
        onPointerDown={onHeaderPointerDown}
        onPointerMove={onHeaderPointerMove}
        onPointerUp={onHeaderPointerUp}
        onPointerCancel={onHeaderPointerUp}
      >
        <div className={styles.headerText}>
          <span className={styles.dragIcon} aria-hidden>
            ☰
          </span>
          <div className={styles.headerTitles}>
            <strong>{L.title}</strong>
            <span className={styles.headerSub}>{L.subtitle}</span>
          </div>
          <span className={styles.dragHint}>{L.dragHint}</span>
        </div>
        <button
          type="button"
          className={styles.toggle}
          aria-label={expanded ? L.collapse : L.expand}
          aria-expanded={expanded}
          onClick={() => setExpanded((open) => !open)}
        >
          {expanded ? "▼" : "▲"}
        </button>
      </header>

      {expanded ? (
        <div className={styles.body}>
          <div className={styles.hero}>
            <p className={styles.heroKicker}>Data Engineer Pilot</p>
            <h2 className={styles.heroTitle}>{L.heroTitle}</h2>
            <p className={styles.heroLead}>{L.heroLead}</p>
            <div className={styles.stack} aria-label={L.stackLabel}>
              {techStack.map((tag) => (
                <span key={tag} className={styles.stackPill}>
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <FeaturedSection block={valueFeatured} />
          <FeaturedSection block={architectureFeatured} />

          <figure className={styles.diagram} aria-label={L.diagramLabel}>
            <figcaption>{L.diagramLabel}</figcaption>
            <pre>{archDiagram}</pre>
          </figure>

          <FeaturedSection block={salesFeatured} />
          <FeaturedSection block={churnFeatured} />
          <FeaturedSection block={segmentationFeatured} />
          <FeaturedSection block={anomalyFeatured} />
          <FeaturedSection block={demandFeatured} />
          <FeaturedSection block={snowflakeFeatured} />
          <FeaturedSection block={postgresEtlFeatured} />
          <FeaturedSection block={cortexPipelineFeatured} />
          <FeaturedSection block={deployFeatured} />

          <p className={styles.scrollHint}>{L.scrollHint}</p>
          <h3 className={styles.workflowTitle}>{L.workflowLabel}</h3>
          {guideSections.map((section) => (
            <div key={section.label} className={styles.section}>
              <p className={styles.sectionLabel}>{section.label}</p>
              <ol className={styles.steps}>
                {section.steps.map((step) => (
                  <li key={step.title}>
                    <strong>{step.title}</strong>
                    <p>{step.body}</p>
                    {step.items?.length ? (
                      <ul className={styles.items}>
                        {step.items.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ol>
            </div>
          ))}
          <p className={styles.footer}>{L.footer}</p>
        </div>
      ) : null}
    </div>
  );
}
