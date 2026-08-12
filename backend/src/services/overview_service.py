from __future__ import annotations

from dataclasses import dataclass

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
    metrics — the overview page never needs its own model."""
    total_customers = len(dataset.customers)
    active_customers = int(dataset.customers["is_active"].sum())
    total_orders = len(dataset.orders)
    total_revenue = float(dataset.orders["order_amount"].sum())

    auc = churn_metrics.get("auc", float("nan"))
    silhouette = segmentation_metrics.get("silhouette_score", float("nan"))
    contamination = anomaly_metrics.get("contamination", 0.0)

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
        source="demo",
        model="overview",
        generated_at=dataset.as_of_date.isoformat(),
        total_customers=total_customers,
        active_customers=active_customers,
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        summaries=summaries,
    )
    return OverviewState(response=response)
