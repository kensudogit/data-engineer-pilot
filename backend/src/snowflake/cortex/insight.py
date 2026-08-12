"""SNOWFLAKE.CORTEX.COMPLETE-based narrative insight generation.

Only ever called when execution_mode="snowflake" (see each service's
_prepare_snowflake()). Every build_prompt_* function reads only
already-computed aggregate metrics (AUC, silhouette score, MAE/RMSE, cluster
sizes, counts) — never raw customer rows or PII — since the resulting text
is meant to summarize a model's results, not analyze individual customers.
"""

from __future__ import annotations


def generate_insight(session, prompt: str, model: str) -> str:
    """Runs SNOWFLAKE.CORTEX.COMPLETE(model, prompt) and returns the text.

    A failure here is deliberately allowed to propagate (never caught to
    fall back to a template sentence under a source="snowflake" label) —
    see snowflake/client.py's SnowflakeNotConfiguredError docstring for why.
    """
    row = session.sql("SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS insight", params=[model, prompt]).collect()
    return row[0]["INSIGHT"]


_SYSTEM_PREAMBLE = "あなたはデータアナリストです。以下のモデル結果を踏まえ、数値を引用しながら1〜2文の簡潔な日本語の要約コメントを書いてください。"


def build_prompt_sales_forecast(channel: str, horizon_days: int, mae: float, rmse: float) -> str:
    return (
        f"{_SYSTEM_PREAMBLE}\n"
        f"売上予測モデル(Holt-Winters相当のARIMA_PLUS系)は{channel}チャネルについて、"
        f"直近ホールドアウト検証でMAE {mae:,.0f}円・RMSE {rmse:,.0f}円の精度で"
        f"今後{horizon_days}日間の売上を予測しました。"
    )


def build_prompt_churn(auc: float, high_risk_count: int, total_scored: int) -> str:
    return (
        f"{_SYSTEM_PREAMBLE}\n"
        f"解約予測モデル(ロジスティック回帰, AUC={auc:.2f})により、"
        f"スコアリング対象{total_scored}件のうち{high_risk_count}件を高リスク顧客として検出しました。"
    )


def build_prompt_segmentation(silhouette: float, cluster_sizes: dict[str, int]) -> str:
    sizes_text = "、".join(f"{label} {size}件" for label, size in cluster_sizes.items())
    return (
        f"{_SYSTEM_PREAMBLE}\n"
        f"顧客分類モデル(KMeans, シルエットスコア={silhouette:.2f})により、"
        f"顧客を{sizes_text}の4クラスタに分類しました。"
    )


def build_prompt_anomaly(contamination: float, detected_count: int, recall: float | None) -> str:
    recall_text = f"注入検証用異常に対する再現率は{recall * 100:.1f}%です。" if recall is not None else ""
    return (
        f"{_SYSTEM_PREAMBLE}\n"
        f"異常検知モデル(IsolationForest, 想定異常率{contamination * 100:.1f}%)により、"
        f"{detected_count}件の取引を異常として検出しました。{recall_text}"
    )


def build_prompt_demand_forecast(product_name: str, horizon_days: int, mae: float) -> str:
    return (
        f"{_SYSTEM_PREAMBLE}\n"
        f"需要予測モデルは{product_name}について、ホールドアウトMAE {mae:.1f}個の精度で"
        f"今後{horizon_days}日間の需要を予測しました。"
    )


def build_prompt_overview(
    total_customers: int, total_revenue: float, auc: float, silhouette: float, contamination: float
) -> str:
    return (
        f"{_SYSTEM_PREAMBLE}\n"
        f"顧客{total_customers}件・累計売上¥{total_revenue:,.0f}のデータに対し、"
        f"解約予測(AUC {auc:.2f})・顧客分類(シルエット{silhouette:.2f})・"
        f"異常検知(想定異常率{contamination * 100:.1f}%)の3モデルを学習済みです。"
    )
