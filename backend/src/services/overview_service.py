from __future__ import annotations

from dataclasses import dataclass

from src.config import get_settings
from src.data.synth import SyntheticDataset
from src.schemas.overview import OverviewResponse, UseCaseSummary


@dataclass
class OverviewState:
    response: OverviewResponse


def prepare(
    dataset: SyntheticDataset,
    churn_metrics: dict[str, float],
    segmentation_metrics: dict[str, float],
    anomaly_metrics: dict[str, float],
) -> OverviewState:
    """Computed once at startup from the other services' already-trained
    metrics — the overview page never needs its own model, and the other
    5 services have already been prepare()d by the time main.py's lifespan
    calls this (see the churn_metrics/segmentation_metrics/anomaly_metrics
    args), so this reads execution_mode itself rather than taking a
    `source` parameter — no main.py signature change needed here."""
    settings = get_settings()
    total_customers = len(dataset.customers)
    active_customers = int(dataset.customers["is_active"].sum())
    total_orders = len(dataset.orders)
    total_revenue = float(dataset.orders["order_amount"].sum())

    auc = churn_metrics.get("auc", float("nan"))
    silhouette = segmentation_metrics.get("silhouette_score", float("nan"))
    contamination = anomaly_metrics.get("contamination", 0.0)

    if settings.execution_mode == "snowflake":
        from src.snowflake.client import get_session  # noqa: PLC0415
        from src.snowflake.cortex.insight import build_prompt_overview, generate_insight  # noqa: PLC0415

        session = get_session()
        source = "snowflake"
        ai_insight_generated_by = "cortex"
        ai_insight = generate_insight(
            session,
            build_prompt_overview(total_customers, total_revenue, auc, silhouette, contamination),
            settings.cortex_model,
        )
    else:
        from src.ai.openai_client import enhance_with_openai  # noqa: PLC0415
        from src.ai.prompts import build_prompt_overview  # noqa: PLC0415

        source = settings.execution_mode  # "demo" or "bigquery"
        template_insight = (
            f"顧客{total_customers}件・累計売上¥{total_revenue:,.0f}のデータに対し、"
            f"解約予測(AUC {auc:.2f})・顧客分類(シルエット{silhouette:.2f})・"
            f"異常検知(想定異常率{contamination * 100:.1f}%)の3モデルを学習済みです。"
        )
        ai_insight, ai_insight_generated_by = enhance_with_openai(
            template_insight,
            build_prompt_overview(total_customers, total_revenue, auc, silhouette, contamination),
            settings,
        )

    summaries = [
        UseCaseSummary(
            key="sales-forecast", label="売上予測", headline=f"¥{total_revenue:,.0f}", detail="累計売上（過去2年・チャネル別ARIMA_PLUS相当）"
        ),
        UseCaseSummary(key="churn", label="解約予測", headline=f"AUC {auc:.2f}", detail="ロジスティック回帰による解約確率スコアリング"),
        UseCaseSummary(
            key="segmentation", label="顧客分類", headline="4クラスタ", detail=f"シルエットスコア {silhouette:.2f}（KMeans）"
        ),
        UseCaseSummary(
            key="anomaly", label="異常検知", headline=f"混入率 {contamination * 100:.1f}%", detail="IsolationForestによる取引異常検知"
        ),
        UseCaseSummary(key="demand-forecast", label="需要予測", headline="上位20商品", detail="商品別Holt-Winters予測"),
    ]

    response = OverviewResponse(
        source=source,
        model="overview",
        generated_at=dataset.as_of_date.isoformat(),
        total_customers=total_customers,
        active_customers=active_customers,
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        summaries=summaries,
        ai_insight=ai_insight,
        ai_insight_generated_by=ai_insight_generated_by,
    )
    return OverviewState(response=response)
