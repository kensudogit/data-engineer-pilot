"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { OverviewResponse } from "@/lib/types";
import { OverviewCards } from "@/components/OverviewCards";
import { SourceBadge } from "@/components/SourceBadge";

export default function OverviewPage() {
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .overview()
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, []);

  if (error) return <p className="errorText">{error}</p>;
  if (!data) return <p className="mutedText">読み込み中...</p>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="pageTitle">概要</h1>
          <p className="pageSubtitle">
            合成EC/SaaSデータ（顧客{data.total_customers}件・注文{data.total_orders}件、生成日 {data.generated_at}）に基づく5機能のサマリです。
          </p>
        </div>
        <SourceBadge source={data.source} model={data.model} />
      </div>

      <div className="kpiGrid">
        <div className="card">
          <div className="mutedText">総顧客数</div>
          <div className="pageTitle" style={{ marginTop: 4 }}>
            {data.total_customers.toLocaleString()}
          </div>
        </div>
        <div className="card">
          <div className="mutedText">アクティブ顧客数</div>
          <div className="pageTitle" style={{ marginTop: 4 }}>
            {data.active_customers.toLocaleString()}
          </div>
        </div>
        <div className="card">
          <div className="mutedText">累計注文数</div>
          <div className="pageTitle" style={{ marginTop: 4 }}>
            {data.total_orders.toLocaleString()}
          </div>
        </div>
        <div className="card">
          <div className="mutedText">累計売上</div>
          <div className="pageTitle" style={{ marginTop: 4 }}>
            ¥{data.total_revenue.toLocaleString()}
          </div>
        </div>
      </div>

      <div className="sectionTitle">機能一覧</div>
      <OverviewCards summaries={data.summaries} />
    </div>
  );
}
