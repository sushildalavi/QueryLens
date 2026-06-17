# QueryLens

QueryLens is a reproducible local systems project for PostgreSQL performance observability.
It collects query telemetry, fingerprints normalized SQL, captures safe plan snapshots, and detects deterministic regressions.
It now includes reliability primitives: idempotent ingestion, retry/backoff, and DLQ routing.

## Architecture

PostgreSQL (`pg_stat_statements`, `pgvector`)
-> C++ collector (`libpqxx`, protobuf, Kafka producer)
-> Redpanda/Kafka topics (`query-telemetry`, `collector-heartbeats`, `telemetry-dlq`)
-> FastAPI + aiokafka consumer (idempotent persistence + regression engine)
-> PostgreSQL `querylens` schema
-> React dashboard
-> Prometheus/Grafana

See:
- `docs/ARCHITECTURE.md`
- `docs/OPERATIONS.md`
- `docs/BENCHMARKS.md`
- `docs/REGRESSION_EVALUATION.md`

## Implemented

- C++ telemetry collector with:
  - SQL normalization and SHA-256 fingerprinting
  - vector operator detection (`<=>`, `<->`, `<#>`)
  - safe EXPLAIN gating for SELECT/WITH
  - protobuf telemetry event publishing to Kafka
- FastAPI control plane with:
  - Kafka consumer (`aiokafka`)
  - deterministic regression detection (8 classes incl. vector index bypass)
  - idempotent event ingestion (`event_id` unique key)
  - retry/backoff and DLQ routing
  - Prometheus `/metrics`
- PostgreSQL schema/migrations with snapshot + regression + DLQ tables
- Prometheus + Grafana provisioning and alert rules
- Demo workflows (`make demo`)
- Benchmark/evaluation harnesses:
  - ingestion benchmark script
  - regression evaluation script

## Not implemented

- Exactly-once delivery semantics
- Kubernetes deployment manifests
- gRPC service APIs
- Managed cloud production deployment

## Quickstart

```bash
make setup
make build
make up
make migrate
make seed
make test
make demo
```

## Benchmark / Evaluation

```bash
make benchmark N=10000
make benchmark N=50000
make benchmark-100k
make regression-eval
```

Outputs:
- `benchmark_results/querylens_benchmark_<N>.json` / `.csv`
- `benchmark_results/regression_eval.json` / `.csv`

## Reliability metrics

- `querylens_duplicate_events_total`
- `querylens_ingest_retries_total`
- `querylens_dlq_events_total`
- `querylens_telemetry_persist_failures_total`
- `querylens_kafka_consumer_lag`

## Alerts

Prometheus alert rules:
- high consumer lag
- persistence failures
- DLQ events
- critical regressions
- high API p95 latency

Defined in `infra/prometheus/alerts.yml`.

## Resume-safe bullets (only implemented)

- Built a PostgreSQL observability platform that streams C++-collected query telemetry into Kafka and applies deterministic regression detection on persisted metric/plan snapshots.
- Hardened ingestion reliability with idempotent event keys, bounded retry/backoff, and DLQ routing to avoid silent event loss during consumer persistence failures.
- Added reproducible systems evaluation harnesses for ingestion throughput/latency/lag recovery and rule-engine precision/recall/F1 on seeded regression scenarios.
- Operationalized the stack with Prometheus metrics, Grafana provisioning, alert rules, and Docker Compose workflows for end-to-end reproducible demos.
