from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FingerprintOut(ORMBase):
    id: UUID
    fingerprint_hash: str
    normalized_query: str
    first_seen_at: datetime
    last_seen_at: datetime


class MetricPoint(ORMBase):
    captured_at: datetime
    calls: int
    total_exec_time_ms: float
    mean_exec_time_ms: float
    rows_returned: int
    shared_blks_hit: int
    shared_blks_read: int
    temp_blks_written: int


class PlanSummary(ORMBase):
    id: UUID
    captured_at: datetime
    top_node_type: str | None
    uses_seq_scan: bool
    uses_index_scan: bool
    estimated_total_cost: float | None
    actual_rows: int | None
    estimated_rows: int | None


class PlanDetail(PlanSummary):
    plan_json: list[dict[str, Any]] | dict[str, Any]
    planning_time_ms: float | None
    execution_time_ms: float | None


class RegressionOut(ORMBase):
    id: UUID
    fingerprint_id: UUID
    severity: str
    regression_type: str
    message: str
    old_metric_json: dict[str, Any] | None
    new_metric_json: dict[str, Any] | None
    created_at: datetime


class RegressionListItem(RegressionOut):
    normalized_query: str


class QuerySummary(ORMBase):
    id: UUID
    fingerprint_hash: str
    normalized_query: str
    last_seen_at: datetime
    latest_mean_ms: float | None = None
    latest_calls: int | None = None
    regression_count: int = 0


class QueryDetail(ORMBase):
    fingerprint: FingerprintOut
    latest_metric: MetricPoint | None
    latest_plan: PlanSummary | None
    regression_count: int


class RecommendationOut(BaseModel):
    id: str
    title: str
    severity: str
    confidence: str
    explanation: str
    suggested_action: str
    evidence_fields: list[str]
    safe_sql: str | None = None


class RecommendationList(BaseModel):
    items: list[RecommendationOut]


class AgentTraceStep(BaseModel):
    step_name: str
    input_summary: str
    tool_name: str | None = None
    tool_args_summary: str | None = None
    output_summary: str
    latency_ms: float | None = None
    status: str
    error: str | None = None


class AgentReport(BaseModel):
    regression_summary: str
    evidence_fields: list[str]
    recommendation: RecommendationOut | None
    safe_sql: str | None
    confidence: float
    safety_warnings: list[str]
    trace: list[AgentTraceStep]


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class CollectResult(BaseModel):
    fingerprints: int
    metrics: int
    plans: int
    regressions: int
    duration_ms: float


class ReportResult(BaseModel):
    generated_text: str
    model_name: str | None
    findings: dict[str, Any]


class HealthOut(BaseModel):
    status: str
    db: str = Field(default="ok")


class CollectorStatusOut(ORMBase):
    service_id: str
    environment: str
    database_name: str
    status: str
    message: str | None
    last_seen_at: datetime
