from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.data import features
from src.data.synth import SyntheticDataset
from src.schemas.churn import ChurnCustomer, ChurnResponse

MODEL_NAME = "churn_model"
NUMERIC_FEATURES = ["recency_days", "frequency_90d", "monetary_90d", "avg_order_value", "tenure_days"]
CATEGORICAL_FEATURES = ["plan_type", "region"]


@dataclass
class ChurnState:
    pipeline: Pipeline
    scoring_features: pd.DataFrame  # latest-snapshot features, one row per current customer
    metrics: dict[str, float]


def _build_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        [
            ("num", StandardScaler(), NUMERIC_FEATURES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
        ]
    )
    return Pipeline([("prep", preprocessor), ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])


def prepare(dataset: SyntheticDataset) -> ChurnState:
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

    return ChurnState(pipeline=pipeline, scoring_features=scoring_features, metrics={"auc": round(auc, 4)})


def _risk_tier(prob: float) -> str:
    if prob >= 0.6:
        return "high"
    if prob >= 0.3:
        return "medium"
    return "low"


def score(state: ChurnState, limit: int = 50, min_risk: float = 0.0) -> ChurnResponse:
    X = state.scoring_features[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    probs = state.pipeline.predict_proba(X)[:, 1]

    rows = state.scoring_features.copy()
    rows["churn_probability"] = probs
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

    return ChurnResponse(source="demo", model=MODEL_NAME, customers=customers, metrics=state.metrics)
