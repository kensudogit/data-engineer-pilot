from __future__ import annotations

from src.data import features


def test_daily_sales_shape(dataset):
    df = features.daily_sales(dataset)
    assert {"order_date", "channel", "total_amount"} <= set(df.columns)
    assert (df["total_amount"] > 0).all()


def test_daily_product_demand_limited_to_top_n(dataset):
    df = features.daily_product_demand(dataset, top_n_products=20)
    assert df["product_id"].nunique() <= 20


def test_customer_features_excludes_already_churned_customers(dataset):
    df = features.customer_features(dataset, dataset.as_of_date)
    churned_ids = set(dataset.customers.loc[dataset.customers["churn_date"].notna(), "customer_id"])
    already_churned_by_today = {
        cid
        for cid in churned_ids
        if dataset.customers.set_index("customer_id").loc[cid, "churn_date"] <= dataset.as_of_date
    }
    assert not (set(df["customer_id"]) & already_churned_by_today)


def test_customer_features_no_negative_recency_or_tenure(dataset):
    df = features.customer_features(dataset, dataset.as_of_date)
    assert (df["tenure_days"] >= 0).all()
    assert (df["recency_days"] >= 0).all()


def test_customer_training_dataset_label_not_always_the_same_value(dataset):
    training = features.customer_training_dataset(dataset)
    assert training["churned_next_30d"].nunique() == 2  # both True and False actually occur


def test_order_transaction_features_keeps_injected_anomaly_flag_for_testing(dataset):
    df = features.order_transaction_features(dataset)
    assert "is_injected_anomaly" in df.columns
    assert df["is_injected_anomaly"].any()
