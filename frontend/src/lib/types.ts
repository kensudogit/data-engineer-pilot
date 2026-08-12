export type Source = "demo" | "bigquery" | "snowflake";

export interface Sourced {
  source: Source;
  model: string;
  ai_insight: string | null;
  ai_insight_generated_by: "template" | "cortex" | null;
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
