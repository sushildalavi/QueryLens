from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from aiokafka import AIOKafkaProducer
from sqlalchemy import create_engine, text

from app.config import settings
from app.proto.collector.proto import telemetry_pb2


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    k = max(0, min(len(values) - 1, int(round((p / 100.0) * (len(values) - 1)))))
    return sorted(values)[k]


async def produce_events(run_id: str, n: int):
    producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()
    try:
        started = time.perf_counter()
        for i in range(n):
            ts = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            fp = f"bench-{run_id}-{i}"
            evt = telemetry_pb2.QueryTelemetryEvent(
                database_name="querylens",
                environment=settings.ENVIRONMENT,
                service_id="bench-producer",
                query_fingerprint=fp,
                normalized_sql=f"select benchmark_{run_id}_{i}",
                raw_query_sample=f"select benchmark_{run_id}_{i}",
                calls=1,
                total_exec_time_ms=10.0,
                mean_exec_time_ms=10.0,
                rows=1,
                shared_blks_hit=1,
                shared_blks_read=0,
                temp_blks_read=0,
                temp_blks_written=0,
                is_vector_query=False,
                captured_at=ts,
            )
            payload = evt.SerializeToString()
            key = f"querylens:{settings.ENVIRONMENT}:{fp}".encode()
            await producer.send_and_wait(settings.KAFKA_TOPIC_QUERY_TELEMETRY, payload, key=key)
        await producer.flush()
        finished = time.perf_counter()
    finally:
        await producer.stop()
    return started, finished


def poll_metrics() -> dict[str, float]:
    import urllib.request

    with urllib.request.urlopen("http://127.0.0.1:8000/metrics", timeout=5) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    out: dict[str, float] = {}
    for line in body.splitlines():
        if line.startswith("querylens_kafka_consumer_lag") and not line.startswith("#"):
            out["kafka_lag"] = max(out.get("kafka_lag", 0.0), float(line.rsplit(" ", 1)[-1]))
        if line.startswith("querylens_duplicate_events_total") and not line.startswith("#"):
            out["duplicates"] = float(line.rsplit(" ", 1)[-1])
        if line.startswith("querylens_dlq_events_total") and not line.startswith("#"):
            out["dlq"] = float(line.rsplit(" ", 1)[-1])
        if line.startswith("querylens_telemetry_persist_failures_total") and not line.startswith("#"):
            out["persist_failures"] = float(line.rsplit(" ", 1)[-1])
    return out


def metric_deltas(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    keys = ("duplicates", "dlq", "persist_failures")
    out: dict[str, float] = {}
    for k in keys:
        out[k] = max(0.0, after.get(k, 0.0) - before.get(k, 0.0))
    return out


def acquire_benchmark_lock() -> None:
    engine = create_engine(settings.DATABASE_URL, future=True)
    with engine.begin() as conn:
        ok = conn.execute(text("SELECT pg_try_advisory_lock(42424242)")).scalar_one()
    engine.dispose()
    if not ok:
        raise RuntimeError("another benchmark run is in progress (advisory lock not acquired)")


def release_benchmark_lock() -> None:
    engine = create_engine(settings.DATABASE_URL, future=True)
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_unlock(42424242)"))
    engine.dispose()


def cleanup_old_benchmark_rows() -> None:
    engine = create_engine(settings.DATABASE_URL, future=True)
    with engine.begin() as conn:
        fp_ids = conn.execute(
            text(
                """
                SELECT id
                FROM querylens.query_fingerprints
                WHERE normalized_query LIKE 'select benchmark_%'
                """
            )
        ).scalars().all()
        if fp_ids:
            conn.execute(
                text("DELETE FROM querylens.query_reports WHERE fingerprint_id = ANY(:fp_ids)"),
                {"fp_ids": fp_ids},
            )
            conn.execute(
                text("DELETE FROM querylens.query_regressions WHERE fingerprint_id = ANY(:fp_ids)"),
                {"fp_ids": fp_ids},
            )
            conn.execute(
                text("DELETE FROM querylens.query_plans WHERE fingerprint_id = ANY(:fp_ids)"),
                {"fp_ids": fp_ids},
            )
            conn.execute(
                text("DELETE FROM querylens.query_metrics WHERE fingerprint_id = ANY(:fp_ids)"),
                {"fp_ids": fp_ids},
            )
            conn.execute(
                text("DELETE FROM querylens.query_fingerprints WHERE id = ANY(:fp_ids)"),
                {"fp_ids": fp_ids},
            )
    engine.dispose()


def fetch_latencies(run_id: str) -> list[float]:
    engine = create_engine(settings.DATABASE_URL, future=True)
    q = text(
        """
        SELECT EXTRACT(EPOCH FROM (m.ingested_at - m.captured_at)) * 1000.0 AS lag_ms
        FROM querylens.query_metrics m
        JOIN querylens.query_fingerprints f ON f.id = m.fingerprint_id
        WHERE f.normalized_query LIKE :prefix
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(q, {"prefix": f"select benchmark_{run_id}_%"}).fetchall()
    engine.dispose()
    return [float(r.lag_ms) for r in rows if r.lag_ms is not None]


def fetch_count(run_id: str) -> int:
    engine = create_engine(settings.DATABASE_URL, future=True)
    q = text(
        """
        SELECT count(*)
        FROM querylens.query_metrics m
        JOIN querylens.query_fingerprints f ON f.id = m.fingerprint_id
        WHERE f.normalized_query LIKE :prefix
        """
    )
    with engine.connect() as conn:
        n = conn.execute(q, {"prefix": f"select benchmark_{run_id}_%"}).scalar_one()
    engine.dispose()
    return int(n)


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--events", type=int, default=10000)
    args = p.parse_args()

    acquire_benchmark_lock()
    try:
        cleanup_old_benchmark_rows()
        baseline_metrics = poll_metrics()

        run_id = f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}_{uuid4().hex[:8]}"
        t0, t1 = await produce_events(run_id, args.events)
        produce_duration = t1 - t0

        lag_peak = 0.0
        wait_start = time.perf_counter()
        lag_recovered_at = None
        while True:
            count = fetch_count(run_id)
            m = poll_metrics()
            lag_peak = max(lag_peak, m.get("kafka_lag", 0.0))
            if count >= args.events and m.get("kafka_lag", 0.0) <= 0.0:
                lag_recovered_at = time.perf_counter()
                break
            if time.perf_counter() - wait_start > 600:
                break
            time.sleep(1)

        lags_ms = fetch_latencies(run_id)
        final_metrics = poll_metrics()
        deltas = metric_deltas(baseline_metrics, final_metrics)
        consumed_count = fetch_count(run_id)
        out = {
            "run_id": run_id,
            "events": args.events,
            "produce_duration_seconds": round(produce_duration, 3),
            "events_per_second": round(args.events / produce_duration, 2) if produce_duration > 0 else 0.0,
            "ingest_latency_ms_p50": round(percentile(lags_ms, 50), 2),
            "ingest_latency_ms_p95": round(percentile(lags_ms, 95), 2),
            "ingest_latency_ms_p99": round(percentile(lags_ms, 99), 2),
            "kafka_lag_peak": lag_peak,
            "kafka_lag_recovery_seconds": round((lag_recovered_at - wait_start), 3) if lag_recovered_at else None,
            "duplicate_events_skipped_delta": deltas["duplicates"],
            "dlq_events_delta": deltas["dlq"],
            "persistence_failures_delta": deltas["persist_failures"],
            "latency_sample_count": len(lags_ms),
            "consumed_count": consumed_count,
            "count_matches_events": consumed_count == args.events,
        }
    finally:
        release_benchmark_lock()

    out_dir = Path("benchmark_results")
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"querylens_benchmark_{args.events}.json").write_text(json.dumps(out, indent=2))
    with (out_dir / f"querylens_benchmark_{args.events}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out.keys()))
        w.writeheader()
        w.writerow(out)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
