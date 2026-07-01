# PlanTrace Agentic AI Upgrade Plan

## Current relevant capabilities
- Deterministic recommendations already exist in `backend/app/core/recommendations.py`.
- Query, regression, and report endpoints already exist in `backend/app/api/queries.py`, `backend/app/api/regressions.py`, and `backend/app/api/reports.py`.
- Benchmark and evaluation artifacts already exist under `backend/benchmark_results/` and `docs/`.
- Frontend query detail and regressions views already surface backend outputs.

## Safest agentic extension points
- Add a thin performance-analysis workflow on top of the existing recommendation engine.
- Keep SQL safety as a critic stage that only emits a safe SQL suggestion when evidence is explicit.
- Reuse existing query fingerprint, metric, plan, and regression records.
- Keep the agent output deterministic and read-only by default.

## Proposed files to change
- `backend/app/core/performance_agent.py`
- `backend/app/api/queries.py`
- `backend/app/schemas.py`
- `backend/tests/test_performance_agent.py`
- `docs/AGENTIC_DB_PERFORMANCE.md`

## Tests to add
- Seq scan fallback creates a recommendation.
- Temp spill creates a recommendation.
- Vector bypass scenario creates the expected recommendation.
- Unsafe SQL remains null when evidence is incomplete.
- Trace includes all steps.

## Local demo command
- `curl http://localhost:8000/api/queries/{id}/agent-report`

## Risks / unknowns
- The repo already has a deterministic recommendation endpoint, so a new agent layer should avoid duplicating business rules.
- The `safe_sql` field must remain conservative.
- Need to verify whether a new endpoint is worth adding versus extending the current recommendation response.

## What not to claim
- Do not claim autonomous SQL rewriting.
- Do not claim the agent can safely execute database changes.
- Do not claim recommendations are validated on all workloads.
- Do not claim live agent behavior without a trace artifact.
