import type {
  CollectResult,
  MetricPoint,
  Page,
  PlacementSimulation,
  PlacementSimulationRequest,
  PlanDetail,
  PlanSummary,
  QueryDetail,
  QueryDiagnostics,
  QuerySummary,
  RecommendationList,
  RegressionListItem,
  ReportResult,
  CollectorStatusItem,
} from "../types";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

function qs(params?: Record<string, string | number | undefined>): string {
  if (!params) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; db: string }>("/health"),

  queries: (params?: {
    limit?: number;
    offset?: number;
    sort?: string;
    q?: string;
  }) => request<Page<QuerySummary>>(`/api/queries${qs(params)}`),

  query: (fid: string) => request<QueryDetail>(`/api/queries/${fid}`),

  diagnostics: (fid: string) =>
    request<QueryDiagnostics>(`/api/queries/${fid}/diagnostics`),

  recommendations: (fid: string) =>
    request<RecommendationList>(`/api/queries/${fid}/recommendations`),

  metrics: (fid: string, limit = 200) =>
    request<MetricPoint[]>(`/api/queries/${fid}/metrics${qs({ limit })}`),

  plans: (fid: string, limit = 20) =>
    request<PlanSummary[]>(`/api/queries/${fid}/plans${qs({ limit })}`),

  latestPlan: (fid: string) =>
    request<PlanDetail>(`/api/queries/${fid}/plans/latest`),

  regressions: (params?: {
    severity?: string;
    limit?: number;
    offset?: number;
  }) => request<Page<RegressionListItem>>(`/api/regressions${qs(params)}`),

  regression: (rid: string) =>
    request<RegressionListItem>(`/api/regressions/${rid}`),

  collect: () =>
    request<CollectResult>("/api/collect/run", { method: "POST" }),

  generateReport: (fid: string) =>
    request<ReportResult>(`/api/reports/${fid}/generate`, { method: "POST" }),

  getReport: (fid: string) =>
    request<ReportResult>(`/api/reports/${fid}`),

  collectorStatus: () => request<CollectorStatusItem[]>(`/api/collector/status`),

  placementSimulation: (payload?: PlacementSimulationRequest) =>
    request<PlacementSimulation>("/api/placement/simulate", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    }),
};
