# Regression Evaluation

PlanTrace includes deterministic rule evaluation over seeded synthetic scenarios:

- `scripts/evaluate_regression_detection.py`

Scenarios include:
- baseline no-regression
- index->seq scan fallback
- vector index bypass
- severe and medium latency spikes
- row estimate mismatch
- temp spill
- cost spike
- call spike

## Run

```bash
make regression-eval
```

## Outputs

- `benchmark_results/regression_eval.json`
- `benchmark_results/regression_eval.csv`

The script computes precision/recall/F1 over seeded ground truth.
