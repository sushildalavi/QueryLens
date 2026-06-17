from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.core.explain_parser import parse_explain
from app.core.regression_detector import MetricSnapshot, PlanSnapshot, detect_regressions
from app.models import CollectorStatus, QueryFingerprint, QueryMetric, QueryPlan, QueryRegression
from app.observability.metrics import (
    duplicate_events_total,
    failed_explain_captures_total,
    regression_events_total,
)

IngestResult = Literal["inserted", "duplicate"]


def _parse_ts(ts: str) -> datetime:
    if not ts:
        return datetime.now(UTC)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


def event_id_for(event: dict, event_type: str = "query_telemetry") -> str:
    parts = [
        str(event.get("database_name", "")),
        str(event.get("environment", "")),
        str(event.get("query_fingerprint", "")),
        str(event.get("captured_at", "")),
        event_type,
    ]
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _upsert_fp(session: Session, normalized_sql: str, fingerprint_hash: str) -> QueryFingerprint:
    fp = session.query(QueryFingerprint).filter_by(fingerprint_hash=fingerprint_hash).first()
    if fp is None:
        fp = QueryFingerprint(fingerprint_hash=fingerprint_hash, normalized_query=normalized_sql)
        session.add(fp)
        session.flush()
    return fp


def _latest_metric(session: Session, fp_id):
    return (
        session.query(QueryMetric)
        .filter_by(fingerprint_id=fp_id)
        .order_by(QueryMetric.captured_at.desc())
        .first()
    )


def _latest_plan(session: Session, fp_id):
    return (
        session.query(QueryPlan)
        .filter_by(fingerprint_id=fp_id)
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )


def ingest_query_event(session: Session, event: dict) -> IngestResult:
    eid = event_id_for(event)
    if session.query(QueryMetric).filter_by(event_id=eid).first() is not None:
        duplicate_events_total.inc()
        return "duplicate"

    fp = _upsert_fp(session, event["normalized_sql"], event["query_fingerprint"])
    prev_m = _latest_metric(session, fp.id)
    prev_p = _latest_plan(session, fp.id)

    metric = QueryMetric(
        event_id=eid,
        fingerprint_id=fp.id,
        captured_at=_parse_ts(event.get("captured_at", "")),
        calls=int(event.get("calls", 0)),
        total_exec_time_ms=float(event.get("total_exec_time_ms", 0.0)),
        mean_exec_time_ms=float(event.get("mean_exec_time_ms", 0.0)),
        rows_returned=int(event.get("rows", 0)),
        shared_blks_hit=int(event.get("shared_blks_hit", 0)),
        shared_blks_read=int(event.get("shared_blks_read", 0)),
        temp_blks_written=int(event.get("temp_blks_written", 0)),
    )
    session.add(metric)
    session.flush()

    new_plan = None
    explain_json = event.get("explain_json")
    if explain_json:
        parsed = parse_explain(json.loads(explain_json))
        new_plan = QueryPlan(
            fingerprint_id=fp.id,
            captured_at=_parse_ts(event.get("captured_at", "")),
            plan_json=json.loads(explain_json),
            top_node_type=parsed.top_node_type,
            uses_seq_scan=parsed.uses_seq_scan,
            uses_index_scan=parsed.uses_index_scan,
            estimated_total_cost=parsed.estimated_total_cost,
            actual_rows=parsed.actual_rows,
            estimated_rows=parsed.estimated_rows,
            planning_time_ms=parsed.planning_time_ms,
            execution_time_ms=parsed.execution_time_ms,
        )
        session.add(new_plan)
        session.flush()
    else:
        failed_explain_captures_total.inc()

    prev_ms = (
        MetricSnapshot(
            calls=prev_m.calls,
            mean_ms=prev_m.mean_exec_time_ms,
            total_ms=prev_m.total_exec_time_ms,
            rows=prev_m.rows_returned,
            temp_blks_written=prev_m.temp_blks_written,
        )
        if prev_m
        else None
    )
    new_ms = MetricSnapshot(
        calls=metric.calls,
        mean_ms=metric.mean_exec_time_ms,
        total_ms=metric.total_exec_time_ms,
        rows=metric.rows_returned,
        temp_blks_written=metric.temp_blks_written,
    )
    prev_ps = (
        PlanSnapshot(
            uses_seq_scan=prev_p.uses_seq_scan,
            uses_index_scan=prev_p.uses_index_scan,
            estimated_total_cost=prev_p.estimated_total_cost,
            actual_rows=prev_p.actual_rows,
            estimated_rows=prev_p.estimated_rows,
            top_node_type=prev_p.top_node_type,
        )
        if prev_p
        else None
    )
    new_ps = (
        PlanSnapshot(
            uses_seq_scan=new_plan.uses_seq_scan,
            uses_index_scan=new_plan.uses_index_scan,
            estimated_total_cost=new_plan.estimated_total_cost,
            actual_rows=new_plan.actual_rows,
            estimated_rows=new_plan.estimated_rows,
            top_node_type=new_plan.top_node_type,
        )
        if new_plan
        else None
    )

    regs = detect_regressions(prev_ms, new_ms, prev_ps, new_ps, is_vector_query=bool(event.get("is_vector_query", False)))
    for r in regs:
        session.add(
            QueryRegression(
                fingerprint_id=fp.id,
                severity=r["severity"],
                regression_type=r["regression_type"],
                message=r["message"],
                old_metric_json=r["old_metric_json"],
                new_metric_json=r["new_metric_json"],
            )
        )
        regression_events_total.labels(severity=r["severity"], regression_type=r["regression_type"]).inc()

    return "inserted"


def ingest_heartbeat_event(session: Session, event: dict) -> None:
    service_id = event.get("service_id", "unknown")
    environment = event.get("environment", "local")
    row = (
        session.query(CollectorStatus)
        .filter_by(service_id=service_id, environment=environment)
        .first()
    )
    if row is None:
        row = CollectorStatus(
            service_id=service_id,
            environment=environment,
            database_name=event.get("database_name", "unknown"),
        )
        session.add(row)
    row.status = event.get("status", "ok")
    row.message = event.get("message")
    row.database_name = event.get("database_name", row.database_name)
    row.last_seen_at = _parse_ts(event.get("captured_at", ""))
