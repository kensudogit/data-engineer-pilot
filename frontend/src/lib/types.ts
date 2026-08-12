export type Source = "demo" | "bigquery" | "snowflake";

export interface Sourced {
  source: Source;
  model: string;
  ai_insight: string | null;
  ai_insight_generated_by: "template" | "cortex" | "openai" | null;
}

export interface TimeSeriesPoint {
  ts: string;
  value: number;
  p10: number | null;
  p90: number | null;
}

export interface SalesForecastResponse extends Sourced {
  channel: string;
  history: TimeSeriesPoint[];
  forecast: TimeSeriesPoint[];
  metrics: Record<string, number>;
}

export interface ChannelListResponse extends Sourced {
  channels: string[];
}

export interface ChurnCustomer {
  customer_id: string;
  churn_probability: number;
  risk_tier: "low" | "medium" | "high";
  plan_type: string;
  region: string;
  tenure_days: number;
}

export interface ChurnResponse extends Sourced {
  customers: ChurnCustomer[];
  metrics: Record<string, number>;
}

export interface ClusterSummary {
  cluster_id: number;
  label: string;
  size: number;
  avg_recency_days: number;
  avg_frequency_90d: number;
  avg_monetary_90d: number;
}

export interface SegmentCustomer {
  customer_id: string;
  cluster_id: number;
  recency_days: number;
  frequency_90d: number;
  monetary_90d: number;
}

export interface SegmentationResponse extends Sourced {
  clusters: ClusterSummary[];
  customers: SegmentCustomer[];
  metrics: Record<string, number>;
}

export interface AnomalyOrder {
  order_id: string;
  order_date: string;
  customer_id: string;
  order_amount: number;
  score: number;
  is_anomaly: boolean;
}

export interface AnomalyResponse extends Sourced {
  anomalies: AnomalyOrder[];
  metrics: Record<string, number>;
}

export interface ProductOption {
  product_id: string;
  name: string;
}

export interface ProductListResponse extends Sourced {
  products: ProductOption[];
}

export interface DemandForecastResponse extends Sourced {
  product_id: string;
  product_name: string;
  history: TimeSeriesPoint[];
  forecast: TimeSeriesPoint[];
  metrics: Record<string, number>;
}

export interface UseCaseSummary {
  key: string;
  label: string;
  headline: string;
  detail: string;
}

export interface OverviewResponse extends Sourced {
  generated_at: string;
  total_customers: number;
  active_customers: number;
  total_orders: number;
  total_revenue: number;
  summaries: UseCaseSummary[];
}

// Cortex Analyst / Cortex Agent deliberately do NOT extend Sourced — they
// have no demo/bigquery equivalent at all, so `source` is always the
// literal "snowflake" and the backend returns 503 (not a Sourced body)
// when unavailable. See api.ts's askCortexAnalyst/askCortexAgent for how
// that 503 is turned into the CortexUnavailable shape below instead of a
// thrown error, so the /ask page can render an honest "unavailable by
// design" state rather than an error screen.

export interface CortexAnalystResponse {
  source: "snowflake";
  question: string;
  generated_sql: string | null;
  answer: string;
}

export interface CortexAgentResponse {
  source: "snowflake";
  question: string;
  answer: string;
  citations: Record<string, unknown>[];
}

export interface CortexUnavailable {
  available: false;
  message: string;
  execution_mode: string;
}

export type CortexAnalystResult = ({ available: true } & CortexAnalystResponse) | CortexUnavailable;
export type CortexAgentResult = ({ available: true } & CortexAgentResponse) | CortexUnavailable;
