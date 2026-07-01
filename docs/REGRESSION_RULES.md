# PlanTrace Regression Rules

All rules are deterministic — no ML or heuristics. They compare consecutive collector snapshots and flag regressions when thresholds are exceeded.

Thresholds are centralized in `backend/app/config.py` and overridable via environment variables.

## Rules

| Rule | Severity | Threshold | Config Variable | Description |
|------|----------|-----------|-----------------|-------------|
| `severe_latency_spike` | high | >= 5.0x | `REGRESSION_LATENCY_RATIO_HIGH` | Mean latency increased 5x or more over previous snapshot |
| `latency_spike` | medium | >= 2.0x | `REGRESSION_LATENCY_RATIO_MEDIUM` | Mean latency increased 2x or more (but less than 5x) |
| `index_scan_to_seq_scan` | high | — | — | Plan regressed from index scan to sequential scan |
| `vector_hnsw_index_bypass` | critical | — | `REGRESSION_HNSW_SEVERITY` | Vector query lost HNSW/index-assisted access, fell back to seq scan |
| `row_estimate_mismatch` | medium | >= 10.0x | `REGRESSION_ROW_ESTIMATE_RATIO` | Actual rows exceed estimated by 10x+ (stale statistics) |
| `temp_spill` | medium | >= 1000 blocks | `REGRESSION_TEMP_BLKS_DELTA` | Temp block writes increased significantly |
| `call_spike` | low | >= 2.0x | `REGRESSION_CALL_RATIO` | Call count doubled+ (suppressed if severe latency also fires) |
| `cost_spike` | medium | >= 2.0x | `REGRESSION_COST_RATIO` | Estimated plan cost doubled+ |

## Severity Precedence

`critical > high > medium > low`

Results are sorted by severity before returning. When both `severe_latency_spike` and `call_spike` fire for the same query, `call_spike` is suppressed to reduce noise.

## How Detection Works

1. Collector reads `pg_stat_statements` and captures `EXPLAIN (FORMAT JSON)`
2. Backend ingests events and compares against the most recent snapshot for each fingerprint
3. Each rule is evaluated independently; multiple rules can fire for the same query
4. Regression events are persisted with old/new metric snapshots for auditability

## Diagnostics vs. regressions

- Diagnostics are broader plan-health findings such as missing index candidates, nested-loop explosions, and spill signals
- Regressions are thresholded comparisons between consecutive snapshots
- The placement simulator is separate from both systems and runs only on synthetic tenant telemetry
- The internal `querylens` schema and metric names are compatibility details, not public branding

## pgvector / HNSW Bypass

The `vector_hnsw_index_bypass` rule specifically targets queries containing vector operators (`<=>`, `<->`, `<#>`) where:

1. The previous plan used an index scan (HNSW)
2. The current plan falls back to sequential scan
3. This indicates the HNSW index was dropped, disabled, or the planner bypassed it

This is marked `critical` by default because vector seq scans on large tables are catastrophically slow compared to approximate nearest neighbor via HNSW.
