# PlanTrace Architecture

## Data plane

PostgreSQL (`pg_stat_statements`, `pgvector`) -> C++ collector (`libpqxx`, protobuf) -> Kafka/Redpanda topics (`query-telemetry`, `collector-heartbeats`, `telemetry-dlq`).

## Control plane

FastAPI service:
- consumes telemetry with `aiokafka`
- persists snapshots and regressions
- stores diagnostic findings derived from EXPLAIN ANALYZE evidence
- applies deterministic rule engine
- handles retries/backoff
- routes failed events to DLQ
- exposes `/health`, `/metrics`, and API endpoints

## Simulator plane

The placement simulator uses synthetic tenant telemetry to compare first-fit, greedy best-fit, weighted scoring, and local-search rebalance strategies. It is a what-if model for database placement planning, not a live control plane for production clusters.

## Persistence

`querylens` schema includes:
- `query_fingerprints`
- `query_metrics` (`event_id`, `ingested_at`)
- `query_plans`
- `query_regressions`
- `query_reports`
- `collector_status`
- `dlq_events`

The internal schema and metric prefixes stay on `querylens` for backwards compatibility with the existing Docker, migration, and dashboard wiring.

## Ops plane

Prometheus scrapes backend `/metrics`, loads alert rules, and Grafana dashboards are provisioned from repository files.
