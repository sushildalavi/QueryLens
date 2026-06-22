from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from app.core.recommendations import Recommendation, recommend_for_query


@dataclass(frozen=True)
class AgentTraceStep:
    step_name: str
    input_summary: str
    tool_name: str | None
    tool_args_summary: str | None
    output_summary: str
    latency_ms: float | None
    status: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fmt(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, dict):
        keys = ", ".join(sorted(map(str, value.keys())))
        return f"dict({keys})"
    return str(value)


def _confidence_from_recommendation(rec: Recommendation | None, safety_warnings: list[str]) -> float:
    if rec is None:
        base = 0.25
    elif rec.confidence == "high":
        base = 0.9
    elif rec.confidence == "medium":
        base = 0.7
    else:
        base = 0.5
    if safety_warnings:
        base = min(base, 0.55)
    return round(max(0.0, min(1.0, base)), 4)


def build_performance_agent_report(
    *,
    normalized_query: str,
    latest_metric: Any | None,
    latest_plan: Any | None,
    latest_regression: Any | None,
) -> dict[str, Any]:
    trace: list[AgentTraceStep] = []

    t0 = time.perf_counter()
    regression_type = getattr(latest_regression, "regression_type", None)
    severity = getattr(latest_regression, "severity", None)
    regression_summary = (
        f"regression_type={regression_type or 'none'} severity={severity or 'none'}"
    )
    trace.append(
        AgentTraceStep(
            step_name="Plan Reader Agent",
            input_summary=_fmt({"query": normalized_query}),
            tool_name=None,
            tool_args_summary=None,
            output_summary=_fmt(
                {
                    "uses_seq_scan": getattr(latest_plan, "uses_seq_scan", None),
                    "temp_blks_written": getattr(latest_metric, "temp_blks_written", None),
                }
            ),
            latency_ms=round((time.perf_counter() - t0) * 1000, 2),
            status="ok",
        )
    )

    t1 = time.perf_counter()
    trace.append(
        AgentTraceStep(
            step_name="Regression Classifier Agent",
            input_summary=regression_summary,
            tool_name="existing regression record",
            tool_args_summary=_fmt({"regression_type": regression_type}),
            output_summary=regression_summary,
            latency_ms=round((time.perf_counter() - t1) * 1000, 2),
            status="ok",
        )
    )

    t2 = time.perf_counter()
    recommendations = recommend_for_query(
        normalized_query=normalized_query,
        latest_metric=latest_metric,
        latest_plan=latest_plan,
        regression_type=regression_type,
    )
    top_rec = recommendations[0] if recommendations else None
    trace.append(
        AgentTraceStep(
            step_name="Recommendation Agent",
            input_summary=_fmt({"query": normalized_query, "regression_type": regression_type}),
            tool_name="recommend_for_query",
            tool_args_summary=_fmt({"normalized_query": normalized_query, "regression_type": regression_type}),
            output_summary=_fmt([rec.id for rec in recommendations]),
            latency_ms=round((time.perf_counter() - t2) * 1000, 2),
            status="ok",
        )
    )

    safety_warnings: list[str] = []
    safe_sql = None
    if latest_plan is None or latest_metric is None:
        safety_warnings.append("insufficient evidence for SQL suggestion")
    if top_rec is None:
        safety_warnings.append("no deterministic recommendation matched")
    if top_rec is not None and top_rec.safe_sql:
        safe_sql = top_rec.safe_sql
    else:
        safe_sql = None

    t3 = time.perf_counter()
    trace.append(
        AgentTraceStep(
            step_name="SQL Safety Critic",
            input_summary=_fmt({"safe_sql": safe_sql, "warnings": safety_warnings}),
            tool_name=None,
            tool_args_summary=None,
            output_summary="safe_sql=none" if safe_sql is None else "safe_sql=provided",
            latency_ms=round((time.perf_counter() - t3) * 1000, 2),
            status="ok",
        )
    )

    confidence = _confidence_from_recommendation(top_rec, safety_warnings)

    t4 = time.perf_counter()
    trace.append(
        AgentTraceStep(
            step_name="Final Report Agent",
            input_summary=_fmt({"confidence": confidence, "warnings": safety_warnings}),
            tool_name=None,
            tool_args_summary=None,
            output_summary=_fmt({"recommendation": getattr(top_rec, "id", None), "safe_sql": safe_sql}),
            latency_ms=round((time.perf_counter() - t4) * 1000, 2),
            status="ok",
        )
    )

    return {
        "regression_summary": regression_summary,
        "evidence_fields": sorted(
            {
                field
                for rec in recommendations
                for field in rec.evidence_fields
            }
        ),
        "recommendation": top_rec.to_dict() if top_rec else None,
        "safe_sql": safe_sql,
        "confidence": confidence,
        "safety_warnings": safety_warnings,
        "trace": [step.to_dict() for step in trace],
    }
