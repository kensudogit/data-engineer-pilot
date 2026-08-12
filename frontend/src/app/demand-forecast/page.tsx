"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { DemandForecastResponse, ProductOption } from "@/lib/types";
import { ForecastChart } from "@/components/ForecastChart";
import { SourceBadge } from "@/components/SourceBadge";
import { AiInsightCard } from "@/components/AiInsightCard";

export default function DemandForecastPage() {
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [productId, setProductId] = useState<string>("");
  const [data, setData] = useState<DemandForecastResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .demandForecastProducts()
      .then((res) => {
        setProducts(res.products);
        setProductId(res.products[0]?.product_id ?? "");
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, []);

  useEffect(() => {
    if (!productId) return;
    api
      .demandForecast(productId, 14)
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "読み込みに失敗しました"));
  }, [productId]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="pageTitle">需要予測</h1>
          <p className="pageSubtitle">
            売上上位20商品について、商品別の日次需要をARIMA_PLUS想定（デモではHolt-Winters）で予測します。
          </p>
        </div>
        {data && <SourceBadge source={data.source} model={data.model} />}
      </div>

      {error && <p className="errorText">{error}</p>}

      {data && <AiInsightCard insight={data.ai_insight} generatedBy={data.ai_insight_generated_by} />}

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="formGroup" style={{ marginBottom: 0, maxWidth: 320 }}>
          <label>商品を選択</label>
          <select value={productId} onChange={(e) => setProductId(e.target.value)}>
            {products.map((p) => (
              <option key={p.product_id} value={p.product_id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {data ? (
        <div className="card">
          <div className="sectionTitle">
            {data.product_name} ／ MAE {data.metrics.mae} ／ RMSE {data.metrics.rmse}
          </div>
          <ForecastChart history={data.history} forecast={data.forecast} unit="個/日" />
        </div>
      ) : (
        !error && <p className="mutedText">読み込み中...</p>
      )}
    </div>
  );
}
