from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or summarize a QueryLens benchmark.")
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--output-dir", default="benchmarks")
    parser.add_argument("--artifact-name", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pending", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=1800.0)
    return parser


def _command_line(args: argparse.Namespace) -> str:
    parts = [
        "python scripts/run_benchmark.py",
        f"--events {args.events}",
        f"--workers {args.workers}",
    ]
    return " ".join(parts)


def build_artifact(args: argparse.Namespace, live: dict[str, Any] | None = None, *, note: str | None = None) -> dict[str, Any]:
    return {
        "status": live.get("status", "measured") if live else "pending",
        "events": args.events,
        "workers": args.workers,
        "collector_throughput_events_per_sec": live.get("collector_throughput_events_per_sec") if live else None,
        "p95_ingestion_latency_ms": live.get("p95_ingestion_latency_ms") if live else None,
        "regression_detection_latency_ms": live.get("regression_detection_latency_ms") if live else None,
        "dlq_count": live.get("dlq_count") if live else None,
        "dlq_rate": live.get("dlq_rate") if live else None,
        "consumer_lag": live.get("consumer_lag") if live else None,
        "regression_classes_detected": live.get("regression_classes_detected") if live else None,
        "command": _command_line(args),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "note": live.get("note") if live else note,
    }


def render_markdown(artifact: dict[str, Any]) -> str:
    lines = [
        "# QueryLens Benchmark",
        "",
        f"- status: {artifact['status']}",
        f"- events: {artifact['events']}",
        f"- workers: {artifact['workers']}",
    ]
    if artifact.get("note"):
        lines.append(f"- note: {artifact['note']}")
    lines.append("")
    if artifact["status"] != "measured":
        lines.append("Results are pending local execution.")
        return "\n".join(lines)

    lines.extend(
        [
            "## Results",
            "",
            f"- collector throughput events/sec: {artifact['collector_throughput_events_per_sec']}",
            f"- p95 ingestion latency ms: {artifact['p95_ingestion_latency_ms']}",
            f"- regression detection latency ms: {artifact['regression_detection_latency_ms']}",
            f"- dlq count: {artifact['dlq_count']}",
            f"- dlq rate: {artifact['dlq_rate']}",
            f"- consumer lag: {artifact['consumer_lag']}",
            f"- regression classes detected: {artifact['regression_classes_detected']}",
        ]
    )
    return "\n".join(lines)


def _pending_artifact(args: argparse.Namespace, note: str) -> dict[str, Any]:
    return build_artifact(args, note=note)


def _run_live_benchmark(args: argparse.Namespace) -> dict[str, Any] | None:
    benchmark_script = BACKEND_DIR / "app" / "bench" / "telemetry_benchmark.py"
    if not benchmark_script.exists():
        return {
            "status": "pending",
            "note": f"live benchmark unavailable: missing benchmark script at {benchmark_script}",
        }

    try:
        completed = subprocess.run(
            [sys.executable, str(benchmark_script), "--events", str(args.events)],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "pending",
            "note": f"live benchmark timed out after {args.timeout_seconds:.0f}s",
        }
    except Exception as exc:
        return {
            "status": "pending",
            "note": f"live benchmark failed to start: {exc}",
        }

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        tail = stderr or stdout or f"exit code {completed.returncode}"
        return {
            "status": "pending",
            "note": f"live benchmark subprocess failed: {tail[-500:]}",
        }

    result_path = BACKEND_DIR / "benchmark_results" / f"querylens_benchmark_{args.events}.json"
    if not result_path.exists():
        return {
            "status": "pending",
            "note": f"live benchmark finished but did not write {result_path}",
        }

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    return {
        "status": "measured",
        "collector_throughput_events_per_sec": payload.get("events_per_second"),
        "p95_ingestion_latency_ms": payload.get("ingest_latency_ms_p95"),
        "regression_detection_latency_ms": payload.get("produce_duration_seconds", 0) * 1000.0,
        "dlq_count": payload.get("dlq_events_delta"),
        "dlq_rate": (payload.get("dlq_events_delta", 0) / args.events) if args.events else 0.0,
        "consumer_lag": payload.get("kafka_lag_peak"),
        "regression_classes_detected": payload.get("regression_classes_detected", []),
    }


def main() -> None:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = args.artifact_name or f"benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    json_path = output_dir / f"{name}.json"
    md_path = output_dir / f"{name}.md"

    if args.dry_run:
        artifact = _pending_artifact(args, "dry-run requested; live collector was not contacted")
    elif args.pending:
        artifact = _pending_artifact(args, "pending mode requested")
    else:
        live = _run_live_benchmark(args)
        if live and live.get("status") == "measured":
            artifact = build_artifact(args, live=live)
        else:
            artifact = _pending_artifact(args, str((live or {}).get("note", "live benchmark unavailable")))

    json_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(artifact) + "\n", encoding="utf-8")
    print(json_path)
    print(md_path)


if __name__ == "__main__":
    main()
