# PlanTrace Demo Workflow

## Quick start

```bash
make build    # build all Docker images
make demo     # runs full baseline → degraded → regression cycle
```

Open http://localhost:3030 for the dashboard, http://localhost:3000 for Grafana (admin/admin).

## What `make demo` does

1. Starts all services (`docker compose up -d`)
2. Waits for Postgres and Kafka/Redpanda to become healthy
3. Runs Alembic migrations against the internal `querylens` schema retained for compatibility
4. Seeds demo data: 5k users, 500 products, 50k orders, 150k order items, 200k events, 10k vector items
5. Resets `pg_stat_statements` and truncates prior results
6. Ensures relational index (`orders.user_id`) and HNSW index (`vector_items.embedding`) are present
7. Runs 500 baseline workload iterations (indexes intact, no drops)
8. Runs the C++ collector — captures baselines from `pg_stat_statements`, streams protobuf to Kafka
9. Runs 1500 degraded iterations — midway through, drops `orders_user_id_idx` and `vector_items_embedding_hnsw_idx`
10. Runs the C++ collector again — should detect regressions vs. the baseline

## Diagnostics and placement

- Query detail pages now surface stored diagnostics alongside the plan tree and regression history
- The placement simulator page runs against synthetic tenant telemetry and compares first-fit, greedy best-fit, weighted scoring, and local-search strategies
- The placement view is a what-if simulator only; it does not manage real Azure SQL clusters or real tenant databases

## Expected regressions

After the demo completes, the Regressions page should show:

| Rule | Query | Severity |
|------|-------|----------|
| `index_scan_to_seq_scan` | `good_user_orders` | high |
| `vector_hnsw_index_bypass` | `vector_similarity` | critical |
| `latency_spike` / `severe_latency_spike` | various | medium / high |
| `cost_spike` | queries affected by index drops | medium |

## Re-running

```bash
make demo-reset   # truncate results + reset pg_stat_statements
make demo          # run again from scratch
```

## Manual step-by-step

```bash
make up
make migrate
make seed

# baseline
docker compose exec backend python -m app.demo.workload --iterations 500 --no-drop-index
make collect-cpp

# degrade
docker compose exec backend python -m app.demo.workload --iterations 1500
make collect-cpp
```

## Workload queries

The workload runs 16 named query templates from `backend/app/demo/bad_queries.py`:

- `good_user_orders` — indexed lookup, regresses when index is dropped
- `vector_similarity` — HNSW-assisted kNN, regresses when HNSW index is dropped
- `missing_index`, `like_prefix_wildcard`, `sequential_scan` — always full scans
- `large_join`, `country_revenue`, `category_breakdown` — analytic joins
- And more (see `bad_queries.py` for the full list with weights)
