"use client";

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimeSeriesPoint } from "@/lib/types";

function shortDate(ts: string) {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

export function ForecastChart({
  history,
  forecast,
  unit,
}: {
  history: TimeSeriesPoint[];
  forecast: TimeSeriesPoint[];
  unit: string;
}) {
  const data = [
    ...history.map((p) => ({ ts: shortDate(p.ts), history: p.value })),
    ...forecast.map((p) => ({ ts: shortDate(p.ts), forecast: p.value, p10: p.p10, p90: p.p90 })),
  ];

  return (
    <div style={{ width: "100%", height: 280 }}>
      <ResponsiveContainer>
        <ComposedChart data={data}>
          <CartesianGrid stroke="#e2e8f0" />
          <XAxis dataKey="ts" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={24} />
          <YAxis
            tick={{ fill: "#64748b", fontSize: 11 }}
            width={64}
            label={{ value: unit, angle: -90, position: "insideLeft", fill: "#64748b" }}
          />
          <Tooltip
            contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 8 }}
          />
          <Legend />
          <Area type="monotone" dataKey="p90" stroke="none" fill="rgba(14,165,233,0.10)" name="P90" />
          <Area type="monotone" dataKey="p10" stroke="none" fill="rgba(255,255,255,1)" name="P10" />
          <Line type="monotone" dataKey="history" stroke="#64748b" dot={false} strokeWidth={1.5} name="実績" />
          <Line type="monotone" dataKey="forecast" stroke="#0ea5e9" dot={false} strokeWidth={2.2} name="予測" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
