import type {
  AnomalyResponse,
  ChannelListResponse,
  ChurnResponse,
  CortexAgentResponse,
  CortexAgentResult,
  CortexAnalystResponse,
  CortexAnalystResult,
  DemandForecastResponse,
  OverviewResponse,
  ProductListResponse,
  SalesForecastResponse,
  SegmentationResponse,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(res: Response): Promise<{ message: string; detail: unknown }> {
  let message = `${res.status} ${res.statusText}`;
  let detail: unknown;
  try {
    const body = await res.json();
    detail = body?.detail;
    if (typeof body?.detail === "string") message = body.detail;
  } catch {
    // ignore — fall back to the status text above
  }
  return { message, detail };
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const { message, detail } = await parseErrorDetail(res);
    throw new ApiError(res.status, message, detail);
  }
  return res.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const { message, detail } = await parseErrorDetail(res);
    throw new ApiError(res.status, message, detail);
  }
  return res.json() as Promise<T>;
}

/** Turns the backend's 503 (Cortex Analyst/Agent has no demo equivalent —
 * see api/cortex_analyst.py / api/cortex_agent.py) into an honest
 * CortexUnavailable value instead of a thrown error, so /ask can render
 * an "unavailable by design" state rather than an error screen. Any other
 * failure status still throws, same as every other endpoint in this app. */
async function askCortex<TResponse extends { source: "snowflake" }>(
  path: string,
  question: string,
): Promise<({ available: true } & TResponse) | { available: false; message: string; execution_mode: string }> {
  try {
    const res = await postJson<TResponse>(path, { question });
    return { available: true, ...res };
  } catch (err) {
    if (err instanceof ApiError && err.status === 503) {
      const detail = err.detail as { message?: string; execution_mode?: string } | undefined;
      return {
        available: false,
        message: detail?.message ?? "現在この機能は利用できません。",
        execution_mode: detail?.execution_mode ?? "unknown",
      };
    }
    throw err;
  }
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

  askCortexAnalyst: (question: string): Promise<CortexAnalystResult> =>
    askCortex<CortexAnalystResponse>("/api/cortex-analyst/ask", question),
  askCortexAgent: (question: string): Promise<CortexAgentResult> =>
    askCortex<CortexAgentResponse>("/api/cortex-agent/ask", question),
};
