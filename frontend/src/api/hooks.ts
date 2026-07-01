import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

const STALE = 30_000;

export function useQueries(params?: {
  limit?: number;
  offset?: number;
  sort?: string;
  q?: string;
}) {
  return useQuery({
    queryKey: ["queries", params],
    queryFn: () => api.queries(params),
    staleTime: STALE,
  });
}

export function useQuery_(fid: string) {
  return useQuery({
    queryKey: ["query", fid],
    queryFn: () => api.query(fid),
    staleTime: STALE,
    enabled: !!fid,
  });
}

export function useDiagnostics(fid: string) {
  return useQuery({
    queryKey: ["diagnostics", fid],
    queryFn: () => api.diagnostics(fid),
    staleTime: STALE,
    enabled: !!fid,
  });
}

export function useMetrics(fid: string, limit = 200) {
  return useQuery({
    queryKey: ["metrics", fid, limit],
    queryFn: () => api.metrics(fid, limit),
    staleTime: STALE,
    enabled: !!fid,
  });
}

export function useLatestPlan(fid: string) {
  return useQuery({
    queryKey: ["latestPlan", fid],
    queryFn: () => api.latestPlan(fid),
    staleTime: STALE,
    enabled: !!fid,
  });
}

export function useRecommendations(fid: string) {
  return useQuery({
    queryKey: ["recommendations", fid],
    queryFn: () => api.recommendations(fid),
    staleTime: STALE,
    enabled: !!fid,
  });
}

export function useRegressions(params?: {
  severity?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["regressions", params],
    queryFn: () => api.regressions(params),
    staleTime: STALE,
  });
}

export function useCollect() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.collect,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["queries"] });
      qc.invalidateQueries({ queryKey: ["regressions"] });
      qc.invalidateQueries({ queryKey: ["metrics"] });
    },
  });
}

export function useGenerateReport(fid: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.generateReport(fid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["report", fid] });
    },
  });
}

export function useReport(fid: string) {
  return useQuery({
    queryKey: ["report", fid],
    queryFn: () => api.getReport(fid),
    staleTime: STALE,
    enabled: !!fid,
    retry: false,
  });
}

export function useCollectorStatus() {
  return useQuery({
    queryKey: ["collector-status"],
    queryFn: api.collectorStatus,
    staleTime: STALE,
  });
}

export function usePlacementSimulation() {
  return useMutation({
    mutationFn: api.placementSimulation,
  });
}
