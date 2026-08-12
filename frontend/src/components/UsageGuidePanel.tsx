"use client";

/**
 * 画面右下のドラッグ可能な利用手順パネル（localStorage で位置・開閉を保存）。
 * Data Engineer Pilot — アーキテクチャ・デモ/BigQuery経路・5機能の使い方を表示。
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
    | "deploy";
};

const valueFeatured: FeaturedBlock = {
  badge: "Value",
  title: "本ツールの位置づけ",
  body:
    "BigQuery MLを想定した5つの分析ユースケース（売上予測・解約予測・顧客分類・異常検知・需要予測）を、1つの一貫した合成EC/SaaSデータセットの上で一気通貫に確認できるパイロットです。GCPプロジェクトが未接続の現状でも、statsmodels/scikit-learnによる本物の近似計算で「同じ画面・同じAPI形状のまま」機能を検証でき、実GCPに接続すればコードを変えずにBigQuery MLへ切り替えられます。",
  variant: "agent",
  items: [
    "GCP未接続でも検証可能 — DEMO_MODE=true（既定）なら合成データに対しローカルで本物のML計算を実行、ハードコードされた偽の数値ではない",
    "本番切り替えはコード変更なし — 環境変数 DEMO_MODE=false + GCP認証情報を渡すだけでBigQuery MLへ切り替わる設計",
    "混同防止 — 全APIレスポンスに source: \"demo\" | \"bigquery\" が必須で入り、画面上にも常にバッジで明示される",
    "フェイルセーフ — DEMO_MODE=false時にBigQuery接続に失敗した場合はデモ数値へ静かにフォールバックせず、起動自体を失敗させる",
  ],
};

const architectureFeatured: FeaturedBlock = {
  badge: "Architecture",
  title: "Next.js BFF + FastAPI + BigQuery ML（デュアル経路）",
  body:
    "ブラウザは常に同一オリジン（または localhost:3030）のみを見ます。Next.js の rewrites が /api・/health・/docs を同一オリジン経由で FastAPI :8000 へプロキシします。FastAPI起動時（lifespan）に合成データセットを一度だけ生成し、5つのモデルを一度だけ学習してapp.stateに保持するため、リクエスト毎の再学習は発生しません。",
  variant: "architecture",
  items: [
    "Next.js — / (概要) · /sales-forecast · /churn · /segmentation · /anomaly · /demand-forecast",
    "FastAPI :8000 — /api/overview 他5エンドポイント・Swagger",
    "デモ経路 — statsmodels(ExponentialSmoothing) / scikit-learn(LogisticRegression・KMeans・IsolationForest) を合成データに対しその場で計算",
    "BigQuery経路 — google-cloud-bigquery 経由で ARIMA_PLUS / LOGISTIC_REG / KMEANS / AUTOENCODER の CREATE MODEL + ML.FORECAST/ML.PREDICT/ML.DETECT_ANOMALIES を実行",
    "Health — GET /health（demo_modeの現在値を含む、frontend経由でも到達可）",
    "Swagger — http://localhost:8030/docs",
  ],
};

const salesFeatured: FeaturedBlock = {
  badge: "1",
  title: "売上予測（/sales-forecast）",
  body:
    "チャネル別（オンライン/店舗等）の日次売上を、過去実績から将来へ延長予測します。BigQuery MLでは ARIMA_PLUS（time_series_id_col='channel', auto_arima=TRUE, holiday_region='JP'）、デモ経路では statsmodels の Holt-Winters（ExponentialSmoothing）を各チャネルごとに学習します。",
  variant: "rag",
  items: [
    "チャネル選択 — プルダウンで対象チャネルを切り替え",
    "予測期間 — horizon_days（既定30日）をドロップダウンで変更可能",
    "グラフ — 実績（history）と予測（forecast）を1本の線で連続表示、予測区間はp10〜p90の80%信頼区間帯（Area）",
    "精度指標 — ホールドアウト（直近14日）でのMAE・RMSEを画面上部に表示",
  ],
};

const churnFeatured: FeaturedBlock = {
  badge: "2",
  title: "解約予測（/churn）",
  body:
    "各顧客の今後30日以内の解約確率をスコアリングします。BigQuery MLでは LOGISTIC_REG（input_label_cols=['churned_next_30d'], auto_class_weights=TRUE）、デモ経路では scikit-learn の LogisticRegression（class_weight='balanced'）を使用。ラベルはリーク無しの時点指定特徴量（point-in-time features）から学習しています。",
  variant: "guard",
  items: [
    "リスクフィルタ — min_risk（低・中・高）で絞り込み可能",
    "件数 — limit で表示件数を調整",
    "テーブル — 顧客ID・解約確率・リスク帯（high/medium/low）・プラン種別・地域・在籍日数を一覧表示",
    "精度指標 — ホールドアウトAUC（seed=42実測で約0.69）を画面上部に表示",
  ],
};

const segmentationFeatured: FeaturedBlock = {
  badge: "3",
  title: "顧客分類（/segmentation）",
  body:
    "RFM（Recency/Frequency/Monetary）指標をもとに顧客を4クラスタへ分類します。BigQuery MLでは KMEANS（num_clusters=4, standardize_features=TRUE）、デモ経路では StandardScaler + KMeans(4) を使用。クラスタは平均購買額の高い順に「VIP → 優良顧客 → 一般顧客 → 休眠リスク」と一意にラベル付けされます。",
  variant: "embed",
  items: [
    "散布図 — 横軸recency_days・縦軸monetary_90d、バブルサイズがfrequency_90d（recharts ScatterChart + ZAxis）",
    "クラスタサマリ — 各クラスタのラベル・件数・平均購買額をカード表示",
    "精度指標 — シルエットスコア（seed=42実測で約0.46）を画面上部に表示",
    "顧客テーブル — 各顧客がどのクラスタに属するかを一覧で確認可能",
  ],
};

const anomalyFeatured: FeaturedBlock = {
  badge: "4",
  title: "異常検知（/anomaly）",
  body:
    "注文（取引）単位で金額・数量の異常を検知します。BigQuery MLでは AUTOENCODER（hidden_units=[16,8,4,8,16]）+ ML.DETECT_ANOMALIES、デモ経路では scikit-learn の IsolationForest（contamination=0.015）を使用。合成データ生成時に約1.5%の注文へ意図的に3〜5倍の金額/数量異常を混入させており、その再現率をpytestで測定しています。",
  variant: "prompt",
  items: [
    "期間フィルタ — window_days で直近N日分に絞り込み",
    "件数 — limit で表示件数を調整",
    "散布図 — 通常（グレー）と異常検知（赤）を色分け表示",
    "精度指標 — 異常スコアのcontamination設定と、混入させた既知異常に対する再現率（seed=42実測で約0.29、無作為検知の約1.5%と比べ約10〜20倍）を画面上部に表示",
  ],
};

const demandFeatured: FeaturedBlock = {
  badge: "5",
  title: "需要予測（/demand-forecast）",
  body:
    "商品別の日次販売数量を将来へ延長予測します。BigQuery MLでは ARIMA_PLUS（time_series_id_col='product_id'）、デモ経路では statsmodels の Holt-Winters を商品ごとに学習。コスト対策として売上上位20商品に限定しています（time_series_id_col使用時、系列数に比例して学習コストが増えるため）。",
  variant: "eval",
  items: [
    "商品選択 — プルダウンで対象商品（上位20商品）を切り替え",
    "予測期間 — horizon_days（既定30日）をドロップダウンで変更可能",
    "グラフ — 売上予測と同じComposedChartパターン（実績・予測・p10/p90信頼区間帯）",
    "除外ルール — 履歴データ点数が一定未満の商品は学習対象から自動的に除外（MIN_HISTORY_POINTS）",
  ],
};

const deployFeatured: FeaturedBlock = {
  badge: "Deploy",
  title: "Docker Compose / ローカル開発",
  body:
    "backend / frontend の2コンテナ構成です（PostgreSQL不要 — デモ経路はインメモリ、実経路はBigQuery直結のため）。ローカルポートは他案件との衝突を避けるため8030/3030を使用しています。",
  variant: "deploy",
  items: [
    "Compose — docker compose up --build → UI :3030 / API :8030",
    "Backend 単体 — cd backend && uvicorn src.main:app --reload --port 8000（要 Python 3.12venv）",
    "Frontend 単体 — cd frontend && npm run dev",
    "テスト — cd backend && pytest（合成データに対して43件のテストを実行、外部通信・GCP接続なし）",
    "Health — /health（demo_modeを含む）· Swagger UI で API 確認",
  ],
};

const techStack = [
  "Python 3.12 · FastAPI",
  "BigQuery ML（ARIMA_PLUS/LOGISTIC_REG/KMEANS/AUTOENCODER）",
  "statsmodels · scikit-learn（デモ経路）",
  "pandas · numpy（合成データ生成、seed固定）",
  "Next.js 15 · React 19",
  "TypeScript · CSS Modules · recharts",
  "google-cloud-bigquery（実経路）",
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
              ├─ DEMO_MODE=true（既定）
              │     └─ services/*.py — statsmodels / scikit-learn で実計算
              └─ DEMO_MODE=false（実GCP接続時）
                    └─ bigquery/client.py — BigQuery ML (CREATE MODEL / ML.FORECAST /
                                             ML.PREDICT / ML.DETECT_ANOMALIES)
              全レスポンス共通: source: "demo" | "bigquery"`;

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
          "ナビ — 概要 · 売上予測 · 解約予測 · 顧客分類 · 異常検知 · 需要予測",
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
          "Health — http://localhost:8030/health（demo_mode:trueであることを確認、または同一オリジン /health）",
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
          "sourceバッジ — デモモードか実BigQuery MLかを常に明示",
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
        body: "DEMO_MODE=false にすると起動時にBigQuery疎通確認を行います。",
        items: [
          "DEMO_MODE=false / GCP_PROJECT_ID=YOUR_PROJECT / GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json",
          "接続に失敗した場合は起動自体が失敗します（デモ数値への静かなフォールバックはしない設計）",
          "成功すればAPIレスポンスのsourceが\"bigquery\"に切り替わり、画面上のバッジも連動して変わる",
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
          "テスト — cd backend && pytest -v（43件、合成データに対し外部通信なしで実行）",
          "Frontend — cd frontend && npm install && npm run dev",
          "型チェック/ビルド確認 — npx tsc --noEmit && npm run build",
        ],
      },
      {
        title: "前提・制限（必ず読む）",
        body: "本パイロットの現時点のスコープ外事項です。",
        items: [
          "BigQuery ML SQLは未実行・未検証 — 公式構文に基づき作成していますが、実GCP環境での動作確認は利用者側で行ってください",
          "デモ経路の数値は近似 — statsmodels/scikit-learnによる本物の計算ですが、BigQuery MLモデルと同一の予測精度を保証しません",
          "オンライン学習・モデルのバージョニングは未実装 — 再学習が必要な場合はプロセスの再起動で対応",
          "需要予測は売上上位20商品に限定 — コスト対策のため（ARIMA_PLUSのtime_series_id_col使用時、系列数に比例して学習コストが増加）",
          "合成データはseed=42で完全に決定的 — 実データではないため、数値そのものに業務的な意味はない",
        ],
      },
      {
        title: "よくあるエラーと対処",
        body: "画面や数値が期待どおりでないときの確認手順です。",
        items: [
          "画面に「デモモード」バッジしか出ない — DEMO_MODE=trueが既定のため正常動作。実BigQuery MLを見たい場合は上記「実GCP環境への接続方法」を実施",
          "/health が404・接続エラー — バックエンドコンテナが起動しているか docker compose ps / docker logs dep-backend で確認",
          "特定の商品/チャネルが選択肢に出ない — 需要予測は売上上位20商品限定、履歴データ点数が少なすぎる系列はMIN_HISTORY_POINTSにより自動除外",
          "起動が失敗する（DEMO_MODE=false時）— BigQuery接続失敗による意図的な起動失敗です。GOOGLE_APPLICATION_CREDENTIALS・GCP_PROJECT_ID・権限を確認",
          "pytestの精度系テストが失敗する — seed=42での実測値を基準にした閾値のため、合成データ生成ロジックを変更した場合は再学習後の実測値に合わせて閾値を見直してください",
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
    "BigQuery ML想定の5機能（売上予測・解約予測・顧客分類・異常検知・需要予測）を、1つの合成EC/SaaSデータセットの上でデモ/BigQueryの両経路から確認できるパイロット基盤です。GCP未接続でも本物の近似計算で機能検証が完結します。",
  stackLabel: "Tech stack",
  diagramLabel: "Service topology",
  workflowLabel: "詳細利用手順",
  scrollHint: "↓ 5機能それぞれの使い方・実GCPへの接続方法・運用手順は下へ",
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
