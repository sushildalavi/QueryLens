# QueryLens Agentic DB Performance

The QueryLens agentic report is a deterministic wrapper around the existing recommendation engine.

## Workflow

1. Plan Reader Agent
2. Regression Classifier Agent
3. Recommendation Agent
4. SQL Safety Critic
5. Final Report Agent

## Output fields

- regression summary
- evidence fields
- recommendation
- safe SQL or null
- confidence
- safety warnings
- trace

## Guardrails

- The workflow is read-only.
- `safe_sql` stays null unless the evidence is explicit.
- The report is built from existing query fingerprint, metric, plan, and regression records.

## Local demo

`GET /api/queries/{fid}/agent-report`
