"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ChurnResponse } from "@/lib/types";
import { ChurnRiskTable } from "@/components/ChurnRiskTable";
import { SourceBadge } from "@/components/SourceBadge";
import { AiInsightCard } from "@/components/AiInsightCard";

export default function ChurnPage() {
  const [minRisk, setMinRisk] = useState(0);
  const [data, setData] = useState<ChurnResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .churn(100, minRisk)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, [minRisk]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="pageTitle">解約予測</h1>
          <p className="pageSubtitle">
            RFM系特徴量から今後30日以内の解約確率をLOGISTIC_REG想定（デモではロジスティック回帰）でスコアリングします。
          </p>
        </div>
        {data && <SourceBadge source={data.source} model={data.model} />}
      </div>

      {error && <p className="errorText">{error}</p>}

      {data && <AiInsightCard insight={data.ai_insight} generatedBy={data.ai_insight_generated_by} />}

      {data && (
        <div className="card" style={{ marginBottom: 20 }}>
          <span className="mutedText">ホールドアウトAUC: {data.metrics.auc?.toFixed(3)}</span>
        </div>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <label className="mutedText">最小リスク:</label>
          {[0, 0.3, 0.6].map((v) => (
            <button
              key={v}
              type="button"
              className={`btn btnOutline btnSmall ${v === minRisk ? "active" : ""}`}
              onClick={() => setMinRisk(v)}
            >
              {v === 0 ? "全て" : v === 0.3 ? "中リスク以上" : "高リスクのみ"}
            </button>
          ))}
        </div>
      </div>

      {data ? (
        <div className="card">
          <div className="sectionTitle">上位{data.customers.length}件</div>
          <ChurnRiskTable customers={data.customers} />
        </div>
      ) : (
        !error && <p className="mutedText">読み込み中...</p>
      )}
    </div>
  );
}
