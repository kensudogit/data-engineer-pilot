from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import Settings, get_settings
from src.data import features
from src.data.synth import SyntheticDataset
from src.schemas.churn import ChurnCustomer, ChurnResponse

MODEL_NAME = "churn_model"
NUMERIC_FEATURES = ["recency_days", "frequency_90d", "monetary_90d", "avg_order_value", "tenure_days"]
CATEGORICAL_FEATURES = ["plan_type", "region"]


@dataclass
class ChurnState:
    # scoring_features must already carry a "churn_probability" column —
    # demo mode fills it via pipeline.predict_proba, snowflake mode via
    # churn_model!PREDICT — so score() can filter/sort either source
    # identically without knowing which one produced it.
    scoring_features: pd.DataFrame
    metrics: dict[str, float]
    ai_insight: str
    ai_insight_generated_by: Literal["template", "cortex"]
    source: Literal["demo", "snowflake"]


def _build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("prep", preprocessor), ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])


def prepare(dataset: SyntheticDataset) -> ChurnState:
    settings = get_settings()
    if settings.execution_mode == "snowflake":
        return _prepare_snowflake(dataset, settings)
    return _prepare_demo(dataset, settings)


def _prepare_demo(dataset: SyntheticDataset, settings: Settings) -> ChurnState:
    training = features.customer_training_dataset(dataset)
    X = training[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = training["churned_next_30d"].astype(int)

    auc = float("nan")
    if y.nunique() > 1:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )
        holdout_pipeline = _build_pipeline()
        holdout_pipeline.fit(X_train, y_train)
        probs = holdout_pipeline.predict_proba(X_test)[:, 1]
        if y_test.nunique() > 1:
            auc = float(roc_auc_score(y_test, probs))

    # Refit on all training rows for the model actually used to score current customers.
    pipeline = _build_pipeline()
    pipeline.fit(X, y)

    scoring_features = features.customer_features(dataset, dataset.as_of_date)
    X_score = scoring_features[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    scoring_features = scoring_features.copy()
    scoring_features["churn_probability"] = pipeline.predict_proba(X_score)[:, 1]

    metrics = {"auc": round(auc, 4)}
    high_risk_count = int((scoring_features["churn_probability"] >= 0.6).sum())
    template_insight = (
        f"AUC {auc:.2f}のロジスティック回帰モデルにより、"
        f"{len(scoring_features)}件中{high_risk_count}件を高リスク顧客として検出しました。"
    )
    from src.ai.openai_client import enhance_with_openai  # noqa: PLC0415
    from src.ai.prompts import build_prompt_churn  # noqa: PLC0415

    ai_insight, ai_insight_generated_by = enhance_with_openai(
        template_insight, build_prompt_churn(auc, high_risk_count, len(scoring_features)), settings
    )

    return ChurnState(
        scoring_features=scoring_features,
        metrics=metrics,
        ai_insight=ai_insight,
        ai_insight_generated_by=ai_insight_generated_by,
        source="demo",
    )


def _prepare_snowflake(dataset: SyntheticDataset, settings: Settings) -> ChurnState:
    """Queries the churn_model Cortex ML Function (SNOWFLAKE.ML.CLASSIFICATION)
    already created by provision_snowflake.py --create-models — scores all
    current customers once here (not per-request), same structure as the
    demo path's scoring_features. Never executed/verified this session; the
    exact shape of churn_model!PREDICT()'s OBJECT_CONSTRUCT(*) result and
    !SHOW_EVALUATION_METRICS() should be re-checked against current
    Snowflake docs before relying on this against a real account.
    """
    from src.snowflake.client import get_session  # noqa: PLC0415
    from src.snowflake.cortex.insight import build_prompt_churn, generate_insight  # noqa: PLC0415

    session = get_session()

    rows = session.sql(
        "SELECT customer_id, plan_type, region, tenure_days, "
        "churn_model!PREDICT(OBJECT_CONSTRUCT(*)) AS prediction "
        "FROM mart.customer_features "
        "WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM mart.customer_features)"
    ).collect()
    scoring_features = pd.DataFrame([r.as_dict() for r in rows])
    scoring_features.columns = [c.lower() for c in scoring_features.columns]
    # prediction is expected to be a Cortex-returned VARIANT/OBJECT with a
    # churn-probability field — the exact key name should be confirmed
    # against a live account; "churn_probability" assumed here.
    scoring_features["churn_probability"] = scoring_features["prediction"].apply(
        lambda p: float(p.get("churn_probability", p.get("probability", 0.0)))
    )

    eval_rows = session.sql("CALL churn_model!SHOW_EVALUATION_METRICS()").collect()
    eval_df = pd.DataFrame([r.as_dict() for r in eval_rows])
    eval_df.columns = [c.lower() for c in eval_df.columns]
    auc = float(eval_df["auc"].iloc[0]) if "auc" in eval_df.columns and len(eval_df) else float("nan")

    metrics = {"auc": round(auc, 4)}
    high_risk_count = int((scoring_features["churn_probability"] >= 0.6).sum())
    ai_insight = generate_insight(
        session,
        build_prompt_churn(auc, high_risk_count, len(scoring_features)),
        settings.cortex_model,
    )

    return ChurnState(
        scoring_features=scoring_features,
        metrics=metrics,
        ai_insight=ai_insight,
        ai_insight_generated_by="cortex",
        source="snowflake",
    )


def _risk_tier(prob: float) -> str:
    if prob >= 0.6:
        return "high"
    if prob >= 0.3:
        return "medium"
    return "low"


def score(state: ChurnState, limit: int = 50, min_risk: float = 0.0) -> ChurnResponse:
    rows = state.scoring_features
    rows = rows[rows["churn_probability"] >= min_risk].sort_values("churn_probability", ascending=False).head(limit)

    customers = [
        ChurnCustomer(
            customer_id=r["customer_id"],
            churn_probability=round(float(r["churn_probability"]), 4),
            risk_tier=_risk_tier(float(r["churn_probability"])),
            plan_type=r["plan_type"],
            region=r["region"],
            tenure_days=int(r["tenure_days"]),
        )
        for _, r in rows.iterrows()
    ]

    return ChurnResponse(
        source=state.source,
        model=MODEL_NAME,
        customers=customers,
        metrics=state.metrics,
        ai_insight=state.ai_insight,
        ai_insight_generated_by=state.ai_insight_generated_by,
    )
