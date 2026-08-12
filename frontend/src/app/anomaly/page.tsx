"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { AnomalyResponse } from "@/lib/types";
import { AnomalyChart } from "@/components/AnomalyChart";
import { SourceBadge } from "@/components/SourceBadge";
import { AiInsightCard } from "@/components/AiInsightCard";

export default function AnomalyPage() {
  const [windowDays, setWindowDays] = useState(90);
  const [data, setData] = useState<AnomalyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .anomalies(windowDays, 300)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, [windowDays]);

  if (error) return <p className="errorText">{error}</p>;
  if (!data) return <p className="mutedText">読み込み中...</p>;

  const flaggedCount = data.anomalies.filter((a) => a.is_anomaly).length;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="pageTitle">異常検知</h1>
          <p className="pageSubtitle">
            注文単位の特徴量をAUTOENCODER想定（デモではscikit-learn IsolationForest）で異常検知します。
          </p>
        </div>
        <SourceBadge source={data.source} model={data.model} />
      </div>

      <AiInsightCard insight={data.ai_insight} generatedBy={data.ai_insight_generated_by} />

      <div className="card" style={{ marginBottom: 20 }}>
        <span className="mutedText">
          混入率設定: {(data.metrics.contamination * 100).toFixed(1)}%
          {data.metrics.recall_on_injected_anomalies !== undefined && (
            <> ／ 既知異常に対する再現率（デモ検証用）: {(data.metrics.recall_on_injected_anomalies * 100).toFixed(1)}%</>
          )}
        </span>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <label className="mutedText">期間:</label>
          {[30, 90, 365].map((d) => (
            <button
              key={d}
              type="button"
              className={`btn btnOutline btnSmall ${d === windowDays ? "active" : ""}`}
              onClick={() => setWindowDays(d)}
            >
              直近{d}日
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <div className="sectionTitle">
          {data.anomalies.length}件中 {flaggedCount}件を異常として検知
        </div>
        <AnomalyChart anomalies={data.anomalies} />
      </div>
    </div>
  );
}
