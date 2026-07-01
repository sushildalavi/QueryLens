# PlanTrace Benchmarks

## Status

- Benchmark artifacts exist, but no canonical numeric summary was extracted in this pass.
- The benchmark runner now has a pending mode and a live mode that reuses the telemetry benchmark when the local stack is up.
- Benchmark artifacts are generated locally from seeded scenarios; no production throughput claims are made here.

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

## Artifact names

- `backend/app/bench/telemetry_benchmark.py` writes `benchmark_results/plantrace_benchmark_*.json` and `.csv`
- `scripts/run_benchmark.py` reads those artifacts when live mode is available
