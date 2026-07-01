# Benchmarks

## Status

- Benchmark artifacts exist, but no canonical numeric summary was extracted in this pass.
- The benchmark runner now has a pending mode and a live mode that reuses the telemetry benchmark when the local stack is up.

## Target metrics

- query events streamed
- collector throughput events/sec
- p95 ingestion latency
- regression detection latency
- DLQ count/rate
- Kafka consumer lag
- regression classes detected
- diagnostic latency
- placement decision latency
- overloaded-node counts before/after synthetic placement
