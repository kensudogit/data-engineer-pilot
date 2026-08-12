-- 顧客分類 (Customer Segmentation) — KMEANS on RFM-style features.
-- Demo-mode equivalent: scikit-learn StandardScaler + KMeans(4) in
-- backend/src/services/segmentation_service.py, evaluated with silhouette score.

CREATE OR REPLACE MODEL `@project.mart.customer_segments_model`
OPTIONS (
  model_type = 'KMEANS',
  num_clusters = 4,
  standardize_features = TRUE
) AS
SELECT
  recency_days,
  frequency_90d,
  monetary_90d,
  avg_order_value,
  tenure_days
FROM `@project.mart.customer_features`
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `@project.mart.customer_features`);

-- Serving query (assign the latest snapshot's customers to clusters):
-- SELECT customer_id, CENTROID_ID AS cluster_id
-- FROM ML.PREDICT(
--   MODEL `@project.mart.customer_segments_model`,
--   (SELECT * FROM `@project.mart.customer_features`
--    WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `@project.mart.customer_features`))
-- );
