# Recommendations

## What this feature does

PlanTrace now exposes deterministic, rule-based recommendations for a single query fingerprint.

The backend inspects the latest metric snapshot, latest plan snapshot, and latest regression type, then returns suggestions such as:

- index review for filtered sequential scans
- memory tuning when temp blocks are written
- vector operator / index compatibility checks
- statistics refresh when estimated rows diverge from actual rows
- latency-spike investigation when no clear plan change explains the slowdown

## Where it is used

- Backend endpoint: `GET /api/queries/{fid}/recommendations`
- Frontend query detail page: `frontend/src/pages/QueryDetail.tsx`

## Guardrails

- The rules are deterministic and local-only.
- `safe_sql` is only emitted when it is genuinely safe to do so; otherwise it remains null.
