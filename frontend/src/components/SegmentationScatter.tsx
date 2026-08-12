"use client";

import {
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { ClusterSummary, SegmentCustomer } from "@/lib/types";

const CLUSTER_COLORS = ["#0ea5e9", "#f59e0b", "#22c55e", "#a855f7", "#ef4444"];

export function SegmentationScatter({
  clusters,
  customers,
}: {
  clusters: ClusterSummary[];
  customers: SegmentCustomer[];
}) {
  return (
    <div style={{ width: "100%", height: 360 }}>
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" />
          <XAxis
            type="number"
            dataKey="recency_days"
            name="Recency"
            unit="日"
            tick={{ fill: "#64748b", fontSize: 11 }}
            label={{ value: "recency_days（小さいほど最近購入）", position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="monetary_90d"
            name="Monetary"
            tick={{ fill: "#64748b", fontSize: 11 }}
            width={70}
            label={{ value: "monetary_90d", angle: -90, position: "insideLeft", fill: "#64748b", fontSize: 11 }}
          />
          <ZAxis type="number" dataKey="frequency_90d" range={[30, 220]} name="Frequency" />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8 }} />
          <Legend />
          {clusters.map((cluster, idx) => (
            <Scatter
              key={cluster.cluster_id}
              name={`${cluster.label} (${cluster.size})`}
              data={customers.filter((c) => c.cluster_id === cluster.cluster_id)}
              fill={CLUSTER_COLORS[idx % CLUSTER_COLORS.length]}
              fillOpacity={0.7}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
