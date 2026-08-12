from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

# Archetype weights and per-archetype behavior drive real, findable structure
# in the data (RFM separation for clustering, a genuine churn signal, a real
# trend+seasonality pattern for forecasting) rather than pure noise — see
# the plan's "ドメイン設計" section for the reasoning.
ARCHETYPES = ["vip", "regular", "occasional", "dormant_at_risk"]
ARCHETYPE_WEIGHTS = [0.10, 0.40, 0.35, 0.15]
# Relative daily order-probability multiplier per archetype (vip orders often,
# dormant_at_risk rarely and stops entirely after its churn_date).
ARCHETYPE_ACTIVITY = {"vip": 5.0, "regular": 1.8, "occasional": 0.7, "dormant_at_risk": 0.35}

CHANNELS = ["web", "mobile_app", "marketplace"]
REGIONS = ["kanto", "kansai", "chubu", "kyushu", "hokkaido"]
PLAN_TYPES = ["basic", "standard", "premium"]
PLAN_MRR = {"basic": 980, "standard": 2980, "premium": 9800}
PRODUCT_CATEGORIES = ["electronics", "apparel", "home", "beauty", "sports"]
CATEGORY_PRICE_RANGE = {
    "electronics": (3000, 45000),
    "apparel": (1500, 12000),
    "home": (2000, 20000),
    "beauty": (800, 6000),
    "sports": (1500, 18000),
}

N_CUSTOMERS = 600
N_PRODUCTS = 40
HISTORY_DAYS = 730  # 2 years of daily history
ANNUAL_GROWTH_RATE = 0.18  # baked into the order-generation process, not regressed in later
ANOMALY_RATE = 0.015
ANOMALY_MULTIPLIER_RANGE = (3.0, 5.0)


@dataclass
class SyntheticDataset:
    customers: pd.DataFrame
    subscriptions: pd.DataFrame
    products: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame
    as_of_date: date
    seed: int


def generate_dataset(seed: int = 42) -> SyntheticDataset:
    """Deterministic synthetic EC/SaaS dataset. Uses only a local
    np.random.Generator (never the global np.random state) so the same seed
    always reproduces byte-identical DataFrames — verified in test_synth.py.
    """
    rng = np.random.default_rng(seed)
    as_of_date = date.today()
    start_date = as_of_date - timedelta(days=HISTORY_DAYS)

    customers = _generate_customers(rng, start_date, as_of_date)
    products = _generate_products(rng, start_date)
    subscriptions = _generate_subscriptions(rng, customers)
    orders, order_items = _generate_orders(rng, customers, products, start_date, as_of_date)

    return SyntheticDataset(
        customers=customers,
        subscriptions=subscriptions,
        products=products,
        orders=orders,
        order_items=order_items,
        as_of_date=as_of_date,
        seed=seed,
    )


def _generate_customers(rng: np.random.Generator, start_date: date, as_of_date: date) -> pd.DataFrame:
    n = N_CUSTOMERS
    archetype = rng.choice(ARCHETYPES, size=n, p=ARCHETYPE_WEIGHTS)
    # Signups spread across the first 18 months so most customers have real tenure.
    signup_offset_days = rng.integers(0, HISTORY_DAYS - 60, size=n)
    signup_date = [start_date + timedelta(days=int(d)) for d in signup_offset_days]

    churn_date: list[date | None] = []
    is_active: list[bool] = []
    for i in range(n):
        if archetype[i] == "dormant_at_risk" and rng.random() < 0.7:
            # Churn happens sometime between 60 days after signup and today.
            earliest = signup_date[i] + timedelta(days=60)
            span = max((as_of_date - earliest).days, 1)
            c_date = earliest + timedelta(days=int(rng.integers(0, span)))
            churn_date.append(c_date)
            is_active.append(False)
        else:
            churn_date.append(None)
            is_active.append(True)

    plan_type = rng.choice(PLAN_TYPES, size=n, p=[0.35, 0.45, 0.20])
    region = rng.choice(REGIONS, size=n)

    return pd.DataFrame(
        {
            "customer_id": [f"C{i:05d}" for i in range(n)],
            "archetype": archetype,  # generator-internal; API layer must not expose this raw label
            "signup_date": signup_date,
            "churn_date": churn_date,
            "is_active": is_active,
            "plan_type": plan_type,
            "region": region,
        }
    )


def _generate_products(rng: np.random.Generator, start_date: date) -> pd.DataFrame:
    n = N_PRODUCTS
    category = rng.choice(PRODUCT_CATEGORIES, size=n)
    unit_price = np.array(
        [rng.integers(*CATEGORY_PRICE_RANGE[c]) for c in category], dtype=float
    )
    launch_offset_days = rng.integers(0, HISTORY_DAYS // 3, size=n)  # most launched early
    launch_date = [start_date + timedelta(days=int(d)) for d in launch_offset_days]

    return pd.DataFrame(
        {
            "product_id": [f"P{i:04d}" for i in range(n)],
            "name": [f"{category[i].capitalize()} Item {i:04d}" for i in range(n)],
            "category": category,
            "unit_price": unit_price,
            "launch_date": launch_date,
        }
    )


def _generate_subscriptions(rng: np.random.Generator, customers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for idx, c in customers.iterrows():
        end_date = c["churn_date"]
        status = "cancelled" if end_date is not None else "active"
        rows.append(
            {
                "subscription_id": f"S{idx:05d}",
                "customer_id": c["customer_id"],
                "plan": c["plan_type"],
                "mrr": PLAN_MRR[c["plan_type"]],
                "start_date": c["signup_date"],
                "end_date": end_date,
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def _seasonality_multiplier(d: date) -> float:
    weekday_factor = 1.25 if d.weekday() >= 5 else 1.0  # weekend uplift
    month_factor = 1.0
    if d.month == 12:
        month_factor = 1.6  # bonus season
    elif d.month in (7, 8):
        month_factor = 1.3  # summer sale
    return weekday_factor * month_factor


def _generate_orders(
    rng: np.random.Generator,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    start_date: date,
    as_of_date: date,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    order_rows = []
    item_rows = []
    order_seq = 0
    item_seq = 0

    customer_ids = customers["customer_id"].to_numpy()
    activity = customers["archetype"].map(ARCHETYPE_ACTIVITY).to_numpy()
    signup = customers["signup_date"].to_numpy()
    churn = customers["churn_date"].to_numpy()
    regions = customers["region"].to_numpy()

    product_ids = products["product_id"].to_numpy()
    product_prices = products["unit_price"].to_numpy()
    launch = products["launch_date"].to_numpy()

    n_days = (as_of_date - start_date).days
    base_daily_orders = 8.0  # mean orders/day at the start of the window, before growth/seasonality

    for day_offset in range(n_days + 1):
        current_date = start_date + timedelta(days=day_offset)
        growth = 1.0 + ANNUAL_GROWTH_RATE * (day_offset / 365.0)
        expected_orders = base_daily_orders * growth * _seasonality_multiplier(current_date)
        n_orders_today = rng.poisson(expected_orders)
        if n_orders_today == 0:
            continue

        # Only customers who have signed up and (if churned) hadn't yet churned can order today.
        eligible_mask = np.array(
            [
                signup[i] <= current_date and (churn[i] is None or churn[i] > current_date)
                for i in range(len(customer_ids))
            ]
        )
        if not eligible_mask.any():
            continue
        weights = activity[eligible_mask]
        weights = weights / weights.sum()
        chosen_idx = rng.choice(np.flatnonzero(eligible_mask), size=n_orders_today, p=weights)

        available_products = launch <= current_date
        avail_product_idx = np.flatnonzero(available_products)
        if len(avail_product_idx) == 0:
            continue

        for cust_idx in chosen_idx:
            order_seq += 1
            order_id = f"O{order_seq:07d}"
            n_items = int(rng.integers(1, 5))
            chosen_products = rng.choice(avail_product_idx, size=min(n_items, len(avail_product_idx)), replace=False)

            is_anomaly = rng.random() < ANOMALY_RATE
            anomaly_mult = rng.uniform(*ANOMALY_MULTIPLIER_RANGE) if is_anomaly else 1.0

            order_amount = 0.0
            item_count = 0
            for p_idx in chosen_products:
                item_seq += 1
                quantity = int(rng.integers(1, 4)) * (round(anomaly_mult) if is_anomaly else 1)
                quantity = max(quantity, 1)
                unit_price = float(product_prices[p_idx])
                discount_pct = round(float(rng.choice([0, 0, 0, 0.05, 0.1, 0.2])), 2)
                line_amount = unit_price * quantity * (1 - discount_pct) * (anomaly_mult if is_anomaly else 1.0)
                order_amount += line_amount
                item_count += 1
                item_rows.append(
                    {
                        "order_item_id": f"OI{item_seq:08d}",
                        "order_id": order_id,
                        "product_id": product_ids[p_idx],
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "discount_pct": discount_pct,
                    }
                )

            order_rows.append(
                {
                    "order_id": order_id,
                    "customer_id": customer_ids[cust_idx],
                    "order_date": current_date,
                    "channel": rng.choice(CHANNELS, p=[0.55, 0.35, 0.10]),
                    "region": regions[cust_idx],
                    "order_amount": round(order_amount, 2),
                    "item_count": item_count,
                    "status": "completed",
                    "is_injected_anomaly": bool(is_anomaly),
                }
            )

    return pd.DataFrame(order_rows), pd.DataFrame(item_rows)
