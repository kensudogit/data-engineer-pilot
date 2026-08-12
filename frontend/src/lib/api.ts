import type {
  AnomalyResponse,
  ChannelListResponse,
  ChurnResponse,
  DemandForecastResponse,
  OverviewResponse,
  ProductListResponse,
  SalesForecastResponse,
  SegmentationResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // ignore — fall back to the status text above
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  overview: () => getJson<OverviewResponse>("/api/overview"),

  salesForecast: (channel?: string, horizonDays = 30) => {
    const q = new URLSearchParams({ horizon_days: String(horizonDays) });
    if (channel) q.set("channel", channel);
    return getJson<SalesForecastResponse>(`/api/sales-forecast?${q}`);
  },
  salesForecastChannels: () => getJson<ChannelListResponse>("/api/sales-forecast/channels"),

  churn: (limit = 50, minRisk = 0) =>
    getJson<ChurnResponse>(`/api/churn?limit=${limit}&min_risk=${minRisk}`),

  segmentation: () => getJson<SegmentationResponse>("/api/segmentation"),

  anomalies: (windowDays = 30, limit = 100) =>
    getJson<AnomalyResponse>(`/api/anomaly?window_days=${windowDays}&limit=${limit}`),

  demandForecastProducts: () => getJson<ProductListResponse>("/api/demand-forecast/products"),
  demandForecast: (productId?: string, horizonDays = 14) => {
    const q = new URLSearchParams({ horizon_days: String(horizonDays) });
    if (productId) q.set("product_id", productId);
    return getJson<DemandForecastResponse>(`/api/demand-forecast?${q}`);
  },
};
