"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { SalesForecastResponse } from "@/lib/types";
import { ForecastChart } from "@/components/ForecastChart";
import { SourceBadge } from "@/components/SourceBadge";
import { AiInsightCard } from "@/components/AiInsightCard";

export default function SalesForecastPage() {
  const [channels, setChannels] = useState<string[]>([]);
  const [channel, setChannel] = useState<string>("");
  const [horizon, setHorizon] = useState(30);
  const [data, setData] = useState<SalesForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .salesForecastChannels()
      .then((res) => {
        setChannels(res.channels);
        setChannel(res.channels[0] ?? "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, []);

  useEffect(() => {
    if (!channel) return;
    api
      .salesForecast(channel, horizon)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, [channel, horizon]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="pageTitle">売上予測</h1>
          <p className="pageSubtitle">
            チャネル別の日次売上をARIMA_PLUS想定（デモではHolt-Winters季節指数平滑法）で予測します。
          </p>
        </div>
        {data && <SourceBadge source={data.source} model={data.model} />}
      </div>

      {error && <p className="errorText">{error}</p>}

      {data && <AiInsightCard insight={data.ai_insight} generatedBy={data.ai_insight_generated_by} />}

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          {channels.map((c) => (
            <button
              key={c}
              type="button"
              className={`btn btnOutline btnSmall ${c === channel ? "active" : ""}`}
              onClick={() => setChannel(c)}
            >
              {c}
            </button>
          ))}
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))} style={{ marginLeft: "auto" }}>
            <option value={7}>7日先まで</option>
            <option value={14}>14日先まで</option>
            <option value={30}>30日先まで</option>
            <option value={60}>60日先まで</option>
          </select>
        </div>
      </div>

      {data ? (
        <div className="card">
          <div className="sectionTitle">
            {data.channel} チャネル ／ MAE {data.metrics.mae?.toLocaleString()} ／ RMSE {data.metrics.rmse?.toLocaleString()}
          </div>
          <ForecastChart history={data.history} forecast={data.forecast} unit="円/日" />
        </div>
      ) : (
        !error && <p className="mutedText">読み込み中...</p>
      )}
    </div>
  );
}
