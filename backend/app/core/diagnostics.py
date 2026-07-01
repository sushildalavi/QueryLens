from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import QueryDiagnostic
from app.observability.metrics import diagnostic_events_total


@dataclass(frozen=True)
class DiagnosticIssue:
    diagnostic_type: str
    severity: str
    title: str
    explanation: str
    suggested_action: str | None
    evidence_fields: list[str]
    evidence_json: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _query_has_shape(normalized_query: str, *terms: str) -> bool:
    q = normalized_query.lower()
    return any(term in q for term in terms)


def _node_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    children = node.get("Plans") or []
    return [c for c in children if isinstance(c, dict)]


def _walk_spill_evidence(node: dict[str, Any], acc: dict[str, float]) -> None:
    temp_read = float(node.get("Temp Read Blocks") or 0)
    temp_written = float(node.get("Temp Written Blocks") or 0)
    if temp_read or temp_written:
        acc["temp_blocks"] = acc.get("temp_blocks", 0.0) + temp_read + temp_written

    sort_used = float(node.get("Sort Space Used") or 0)
    if sort_used:
        acc["sort_space_used"] = acc.get("sort_space_used", 0.0) + sort_used

    hash_batches = float(node.get("Hash Batches") or 0)
    if hash_batches > 1:
        acc["hash_batches"] = max(acc.get("hash_batches", 0.0), hash_batches)

    for child in _node_children(node):
        _walk_spill_evidence(child, acc)


def _nested_loop_explosion(node: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    if node.get("Node Type") == "Nested Loop":
        children = _node_children(node)
        child_actuals = [
            float(child.get("Actual Rows") or child.get("Plan Rows") or 0)
            for child in children
        ]
        parent_rows = float(node.get("Actual Rows") or node.get("Plan Rows") or 0)
        if child_actuals:
            max_child = max(child_actuals)
            ratio = max_child / max(parent_rows, 1.0)
            if max_child >= 1000 and ratio >= 5.0:
                findings.append(
                    {
                        "diagnostic_type": "nested_loop_explosion",
                        "severity": "high",
                        "title": "Nested loop expansion is amplifying work",
                        "explanation": (
                            "The nested-loop node is multiplying row counts enough to "
                            "suggest a join-order or access-path issue."
                        ),
                        "suggested_action": (
                            "Review join predicates, confirm the selective side is indexed, "
                            "and consider a different join shape when the planner misestimates cardinality."
                        ),
                        "evidence_fields": ["Node Type", "Actual Rows", "Plan Rows"],
                        "evidence_json": {
                            "parent_actual_rows": parent_rows,
                            "max_child_actual_rows": max_child,
                            "child_count": len(children),
                            "ratio": round(ratio, 2),
                        },
                    }
                )
    for child in _node_children(node):
        _nested_loop_explosion(child, findings)


def diagnose_query(
    *,
    normalized_query: str,
    latest_metric: Any | None,
    latest_plan: Any | None,
    previous_plan: Any | None = None,
    plan_json: Any | None = None,
) -> list[DiagnosticIssue]:
    issues: list[DiagnosticIssue] = []
    q = normalized_query.lower()

    if (
        latest_plan is not None
        and getattr(latest_plan, "estimated_rows", None) is not None
        and getattr(latest_plan, "actual_rows", None) is not None
    ):
        estimated = max(float(latest_plan.estimated_rows), 1.0)
        actual = float(latest_plan.actual_rows)
        ratio = actual / estimated
        if ratio >= 10.0:
            issues.append(
                DiagnosticIssue(
                    diagnostic_type="row_estimate_mismatch",
                    severity="medium",
                    title="Row estimate diverges from reality",
                    explanation=(
                        "The optimizer's estimated row count is far from the observed "
                        "row count, which often indicates stale statistics or a poor selectivity estimate."
                    ),
                    suggested_action="Run ANALYZE and inspect predicates or multi-column statistics.",
                    evidence_fields=["Actual Rows", "Plan Rows"],
                    evidence_json={
                        "actual_rows": actual,
                        "estimated_rows": estimated,
                        "ratio": round(ratio, 2),
                    },
                )
            )

    if (
        previous_plan is not None
        and latest_plan is not None
        and getattr(previous_plan, "uses_index_scan", False)
        and getattr(latest_plan, "uses_seq_scan", False)
        and not getattr(latest_plan, "uses_index_scan", False)
    ):
        issues.append(
            DiagnosticIssue(
                diagnostic_type="seq_scan_fallback",
                severity="high",
                title="Sequential scan fallback detected",
                explanation=(
                    "The latest execution plan regressed from index-assisted access to a sequential scan."
                ),
                suggested_action="Check for dropped indexes, changed predicates, or planner selectivity drift.",
                evidence_fields=["uses_index_scan", "uses_seq_scan"],
                evidence_json={
                    "previous_uses_index_scan": True,
                    "latest_uses_seq_scan": True,
                },
            )
        )

    if latest_plan is not None and getattr(latest_plan, "uses_seq_scan", False):
        if _query_has_shape(q, " where ", " join ", " like ", " ilike ") and (
            getattr(latest_metric, "rows_returned", 0) >= 1000
            or (getattr(latest_plan, "actual_rows", 0) or 0) >= 1000
            or (getattr(latest_plan, "estimated_rows", 0) or 0) >= 1000
        ):
            issues.append(
                DiagnosticIssue(
                    diagnostic_type="missing_index_candidate",
                    severity="medium",
                    title="Missing index candidate",
                    explanation=(
                        "The query is filtering or joining enough rows that a sequential scan looks suspicious."
                    ),
                    suggested_action="Evaluate whether an index can support the most selective predicate or join key.",
                    evidence_fields=["normalized_query", "uses_seq_scan", "rows_returned"],
                    evidence_json={
                        "normalized_query": normalized_query,
                        "rows_returned": getattr(latest_metric, "rows_returned", None),
                        "actual_rows": getattr(latest_plan, "actual_rows", None),
                        "estimated_rows": getattr(latest_plan, "estimated_rows", None),
                    },
                )
            )

    spill_evidence: dict[str, float] = {}
    if plan_json:
        root = plan_json[0] if isinstance(plan_json, list) else plan_json
        if isinstance(root, dict):
            plan = root.get("Plan", root)
            if isinstance(plan, dict):
                _walk_spill_evidence(plan, spill_evidence)
                nested_findings: list[dict[str, Any]] = []
                _nested_loop_explosion(plan, nested_findings)
                for item in nested_findings:
                    issues.append(DiagnosticIssue(**item))

    if spill_evidence:
        temp_blocks = spill_evidence.get("temp_blocks", 0.0)
        sort_space_used = spill_evidence.get("sort_space_used", 0.0)
        hash_batches = spill_evidence.get("hash_batches", 0.0)
        if temp_blocks >= 1.0 or sort_space_used >= 1024.0 or hash_batches > 1.0:
            issues.append(
                DiagnosticIssue(
                    diagnostic_type="temp_sort_hash_spill",
                    severity="medium",
                    title="Temp or workfile spill detected",
                    explanation=(
                        "The plan shows spill evidence from sort, hash, or temp workfiles, which usually means memory pressure."
                    ),
                    suggested_action="Review work_mem, reduce result width, or change the access path to avoid the spill.",
                    evidence_fields=["Temp Read Blocks", "Temp Written Blocks", "Sort Space Used", "Hash Batches"],
                    evidence_json={
                        "temp_blocks": temp_blocks,
                        "sort_space_used": sort_space_used,
                        "hash_batches": hash_batches,
                    },
                )
            )

    if (
        latest_plan is not None
        and _query_has_shape(q, "<=>", "<->", "<#>")
        and getattr(latest_plan, "uses_seq_scan", False)
        and previous_plan is not None
        and getattr(previous_plan, "uses_index_scan", False)
    ):
        issues.append(
            DiagnosticIssue(
                diagnostic_type="vector_hnsw_bypass",
                severity="critical",
                title="Vector HNSW bypass detected",
                explanation=(
                    "The vector query fell back from index-assisted access to a sequential scan."
                ),
                suggested_action="Check the vector index, operator class, and query shape for compatibility.",
                evidence_fields=["normalized_query", "uses_seq_scan", "uses_index_scan"],
                evidence_json={
                    "normalized_query": normalized_query,
                    "uses_seq_scan": True,
                    "previous_uses_index_scan": True,
                },
            )
        )

    seen: set[str] = set()
    deduped: list[DiagnosticIssue] = []
    for issue in issues:
        if issue.diagnostic_type in seen:
            continue
        seen.add(issue.diagnostic_type)
        deduped.append(issue)
    return deduped


def persist_diagnostics(
    session: Session,
    *,
    fingerprint_id: UUID,
    plan_id: UUID | None,
    issues: list[DiagnosticIssue],
) -> list[QueryDiagnostic]:
    rows: list[QueryDiagnostic] = []
    for issue in issues:
        row = QueryDiagnostic(
            fingerprint_id=fingerprint_id,
            plan_id=plan_id,
            diagnostic_type=issue.diagnostic_type,
            severity=issue.severity,
            title=issue.title,
            explanation=issue.explanation,
            suggested_action=issue.suggested_action,
            evidence_json=issue.evidence_json,
        )
        session.add(row)
        rows.append(row)
        diagnostic_events_total.labels(severity=issue.severity, diagnostic_type=issue.diagnostic_type).inc()
    return rows
