from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_benchmark import build_artifact  # noqa: E402


def test_querylens_benchmark_artifact_schema():
    artifact = build_artifact(Namespace(events=10000, workers=4, output_dir="benchmarks", artifact_name=""))
    assert artifact["status"] == "pending"
    assert artifact["events"] == 10000
    assert artifact["workers"] == 4
    assert "p95_ingestion_latency_ms" in artifact


def test_querylens_benchmark_artifact_with_live_metrics():
    artifact = build_artifact(
        Namespace(events=100, workers=2, output_dir="benchmarks", artifact_name=""),
        live={
            "status": "measured",
            "collector_throughput_events_per_sec": 52.3,
            "p95_ingestion_latency_ms": 14.2,
            "regression_detection_latency_ms": 88.0,
            "dlq_count": 1,
            "dlq_rate": 0.01,
            "consumer_lag": 0.0,
            "regression_classes_detected": ["temp_spill"],
        },
    )
    assert artifact["status"] == "measured"
    assert artifact["collector_throughput_events_per_sec"] == 52.3
