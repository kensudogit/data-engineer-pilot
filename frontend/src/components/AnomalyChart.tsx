"use client";

import { CartesianGrid, Legend, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import type { AnomalyOrder } from "@/lib/types";

export function AnomalyChart({ anomalies }: { anomalies: AnomalyOrder[] }) {
  const normal = anomalies
    .filter((a) => !a.is_anomaly)
    .map((a) => ({ x: a.order_date, y: a.order_amount, order_id: a.order_id }));
  const flagged = anomalies
    .filter((a) => a.is_anomaly)
    .map((a) => ({ x: a.order_date, y: a.order_amount, order_id: a.order_id }));

  return (
    <div style={{ width: "100%", height: 320 }}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" />
          <XAxis dataKey="x" name="注文日" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={30} />
          <YAxis
            dataKey="y"
            name="注文金額"
            tick={{ fill: "#64748b", fontSize: 11 }}
            width={70}
          />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8 }} />
          <Legend />
          <Scatter name="通常" data={normal} fill="#94a3b8" fillOpacity={0.5} />
          <Scatter name="異常検知" data={flagged} fill="#ef4444" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
