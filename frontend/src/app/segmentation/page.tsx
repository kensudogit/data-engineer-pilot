"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { SegmentationResponse } from "@/lib/types";
import { SegmentationScatter } from "@/components/SegmentationScatter";
import { SourceBadge } from "@/components/SourceBadge";

export default function SegmentationPage() {
  const [data, setData] = useState<SegmentationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .segmentation()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, []);

  if (error) return <p className="errorText">{error}</p>;
  if (!data) return <p className="mutedText">読み込み中...</p>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="pageTitle">顧客分類</h1>
          <p className="pageSubtitle">
            RFM系特徴量をKMEANS想定（デモではscikit-learn KMeans, 4クラスタ）で分類します。
          </p>
        </div>
        <SourceBadge source={data.source} model={data.model} />
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <span className="mutedText">シルエットスコア: {data.metrics.silhouette_score?.toFixed(3)}</span>
      </div>

      <div className="kpiGrid">
        {data.clusters.map((c) => (
          <div key={c.cluster_id} className="card">
            <div className="sectionTitle" style={{ marginBottom: 4 }}>
              {c.label}
            </div>
            <div className="mutedText">{c.size}名</div>
            <div className="mutedText">平均recency: {c.avg_recency_days}日</div>
            <div className="mutedText">平均monetary(90d): ¥{c.avg_monetary_90d.toLocaleString()}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="sectionTitle">Recency × Monetary（バブルサイズ = Frequency）</div>
        <SegmentationScatter clusters={data.clusters} customers={data.customers} />
      </div>
    </div>
  );
}
