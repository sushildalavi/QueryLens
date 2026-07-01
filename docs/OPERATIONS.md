# PlanTrace Operations

## Reliability features implemented

- Idempotent ingestion key (`event_id`) for streamed telemetry
- Duplicate replay skip with metric: `querylens_duplicate_events_total`
- Bounded retry with exponential backoff (`100ms, 500ms, 2s` by default)
- Dead-letter queue routing to Kafka topic `telemetry-dlq`
- DLQ persistence table: `querylens.dlq_events`

## Key env vars

- `KAFKA_TOPIC_QUERY_TELEMETRY`
- `KAFKA_TOPIC_COLLECTOR_HEARTBEAT`
- `KAFKA_TOPIC_TELEMETRY_DLQ`
- `KAFKA_CONSUMER_MAX_RETRIES`
- `KAFKA_RETRY_BACKOFFS_MS`

## Metrics

- `querylens_telemetry_events_consumed_total`
- `querylens_duplicate_events_total`
- `querylens_ingest_retries_total`
- `querylens_dlq_events_total`
- `querylens_telemetry_persist_failures_total`
- `querylens_diagnostic_latency_seconds`
- `querylens_diagnostic_failures_total`
- `querylens_placement_latency_seconds`
- `querylens_placement_failures_total`
- `querylens_kafka_consumer_lag`
- `querylens_api_request_latency_seconds`

The `querylens_*` metric prefix is retained for compatibility with the existing dashboards and alerts.

## Alert rules

Prometheus rules are defined in:
- `infra/prometheus/alerts.yml`
