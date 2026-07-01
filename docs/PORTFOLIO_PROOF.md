# Portfolio Proof

## What the project does

PlanTrace is a PostgreSQL observability system that streams query telemetry, classifies regressions, and surfaces them in a backend plus frontend stack.

## Why it is technically impressive

- The project spans backend collection, regression analysis, and dashboard presentation.
- It includes a C++ collector and a React UI.
- The repo already contains regression evaluation documentation.

## Architecture summary

- Query telemetry -> collector -> backend API -> regression detection/reporting -> frontend dashboard.

## How to run locally

- Use the repo-specific `make` targets documented in `README.md`
- Frontend development via `npm run dev` in `frontend/`

## How to test

- Backend tests via `pytest`
- Frontend build via `npm run build`

## How to benchmark or evaluate

- Review `docs/REGRESSION_EVALUATION.md`
- Review `docs/BENCHMARKS.md`
- Review `docs/RECOMMENDATIONS.md`
- Future benchmark artifacts should live under `benchmarks/`

## Verified metrics only

- No canonical benchmark summary was extracted in this pass.

## Current limitations

- Benchmark generation is now packaged into a runner, but live results still depend on a local database and backend.
- The seed-demo story is stronger now, but it still relies on fixture-backed data.

## Future improvements

- Add a compact benchmark summary doc with parsed artifacts.

## Resume bullets

- Built a PostgreSQL observability stack that detects query regressions from streamed telemetry.
- Combined backend collection, regression analysis, and dashboard visualization in one system.
- Documented seeded regression evaluation workflows for reproducibility.

## Verification Log

- `python3 /Users/sushildalavi/Desktop/Github/plantrace/scripts/run_benchmark.py --pending --events 10000 --workers 4` - pass - 2026-06-17 - Wrote pending JSON and Markdown artifacts under `benchmarks/`.
- `python3 /Users/sushildalavi/Desktop/Github/plantrace/scripts/run_benchmark.py --pending --events 100 --workers 2 --output-dir /tmp/plantrace-bench --artifact-name plantrace_test` - pass - 2026-06-17 - Verified the pending artifact path with a custom output location.
- Direct helper checks against `scripts/run_benchmark.py` - pass - 2026-06-17 - Verified pending and live artifact shapes through direct assertions.
