from __future__ import annotations

from src.services import segmentation_service

# Empirically observed silhouette score on the seed=42 dataset is ~0.46.
MIN_SILHOUETTE = 0.3


def test_prepare_finds_real_cluster_separation(dataset):
    state = segmentation_service.prepare(dataset)
    assert state.metrics["silhouette_score"] > MIN_SILHOUETTE


def test_segments_returns_four_distinctly_labeled_clusters(dataset):
    state = segmentation_service.prepare(dataset)
    resp = segmentation_service.segments(state)

    assert resp.source == "demo"
    assert len(resp.clusters) == segmentation_service.N_CLUSTERS
    labels = [c.label for c in resp.clusters]
    assert len(set(labels)) == len(labels)  # every cluster has a distinct label


def test_cluster_sizes_sum_to_total_customers(dataset):
    state = segmentation_service.prepare(dataset)
    resp = segmentation_service.segments(state)
    assert sum(c.size for c in resp.clusters) == len(resp.customers)


def test_highest_monetary_cluster_is_labeled_vip(dataset):
    state = segmentation_service.prepare(dataset)
    resp = segmentation_service.segments(state)
    top_cluster = max(resp.clusters, key=lambda c: c.avg_monetary_90d)
    assert top_cluster.label == "VIP"
