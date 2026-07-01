export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface QuerySummary {
  id: string;
  fingerprint_hash: string;
  normalized_query: string;
  last_seen_at: string;
  latest_mean_ms: number | null;
  latest_calls: number | null;
  regression_count: number;
}

export interface FingerprintOut {
  id: string;
  fingerprint_hash: string;
  normalized_query: string;
  first_seen_at: string;
  last_seen_at: string;
}

export interface MetricPoint {
  captured_at: string;
  calls: number;
  total_exec_time_ms: number;
  mean_exec_time_ms: number;
  rows_returned: number;
  shared_blks_hit: number;
  shared_blks_read: number;
  temp_blks_written: number;
}

export interface PlanSummary {
  id: string;
  captured_at: string;
  top_node_type: string | null;
  uses_seq_scan: boolean;
  uses_index_scan: boolean;
  estimated_total_cost: number | null;
  actual_rows: number | null;
  estimated_rows: number | null;
}

export interface PlanDetail extends PlanSummary {
  plan_json: unknown;
  planning_time_ms: number | null;
  execution_time_ms: number | null;
}

export interface RegressionListItem {
  id: string;
  fingerprint_id: string;
  severity: "critical" | "high" | "medium" | "low";
  regression_type: string;
  message: string;
  old_metric_json: Record<string, unknown> | null;
  new_metric_json: Record<string, unknown> | null;
  created_at: string;
  normalized_query: string;
}

export interface CollectorStatusItem {
  service_id: string;
  environment: string;
  database_name: string;
  status: string;
  message: string | null;
  last_seen_at: string;
}

export interface QueryDetail {
  fingerprint: FingerprintOut;
  latest_metric: MetricPoint | null;
  latest_plan: PlanSummary | null;
  regression_count: number;
}

export interface DiagnosticOut {
  id: string;
  fingerprint_id: string;
  plan_id: string | null;
  diagnostic_type: string;
  severity: string;
  title: string;
  explanation: string;
  suggested_action: string | null;
  evidence_json: Record<string, unknown>;
  created_at: string;
}

export interface QueryDiagnostics {
  fingerprint: FingerprintOut;
  latest_plan: PlanSummary | null;
  latest_metric: MetricPoint | null;
  diagnostics: DiagnosticOut[];
  diagnostic_count: number;
}

export interface RecommendationItem {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low";
  confidence: "high" | "medium" | "low";
  explanation: string;
  suggested_action: string;
  evidence_fields: string[];
  safe_sql: string | null;
}

export interface RecommendationList {
  items: RecommendationItem[];
}

export interface CollectResult {
  fingerprints: number;
  metrics: number;
  plans: number;
  regressions: number;
  diagnostics: number;
  duration_ms: number;
}

export interface ReportResult {
  generated_text: string;
  model_name: string | null;
  findings: {
    normalized_query: string;
    findings: string[];
  };
}

export interface ResourceVector {
  cpu: number;
  memory: number;
  storage: number;
  iops: number;
  p95_latency_ms: number;
}

export interface TenantTelemetry {
  tenant_id: string;
  database_name: string;
  region: string;
  sql_fingerprint: string;
  normalized_sql: string;
  calls: number;
  mean_exec_time_ms: number;
  p95_latency_ms: number;
  cpu: number;
  memory: number;
  storage: number;
  iops: number;
  migration_cost: number;
}

export interface PlacementNode {
  node_id: string;
  region: string;
  cluster_id: string;
  availability_zone: string;
  capacity: ResourceVector;
  used: ResourceVector;
  overloaded: boolean;
  tenants: string[];
  overload_score: number;
}

export interface PlacementComparison {
  overloaded_nodes_before: number;
  overloaded_nodes_after: number;
  balance_before: number;
  balance_after: number;
  migration_cost: number;
  hotspot_reduction: number;
  p95_decision_latency_ms: number;
}

export interface PlacementAlgorithm {
  algorithm: string;
  nodes: PlacementNode[];
  comparison: PlacementComparison;
}

export interface PlacementSimulation {
  seed: number;
  tenants: number;
  regions: number;
  clusters_per_region: number;
  nodes_per_cluster: number;
  telemetry: TenantTelemetry[];
  algorithms: PlacementAlgorithm[];
}

export interface PlacementSimulationRequest {
  seed?: number;
  tenants?: number;
  regions?: number;
  clusters_per_region?: number;
  nodes_per_cluster?: number;
  algorithms?: string[] | null;
}
