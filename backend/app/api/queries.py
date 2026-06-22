from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.performance_agent import build_performance_agent_report
from app.core.recommendations import recommend_for_query
from app.models import QueryFingerprint, QueryMetric, QueryPlan, QueryRegression
from app.schemas import (
    AgentReport,
    FingerprintOut,
    MetricPoint,
    Page,
    RecommendationList,
    RecommendationOut,
    PlanDetail,
    PlanSummary,
    QueryDetail,
    QuerySummary,
)

router = APIRouter(prefix="/api/queries", tags=["queries"])


def _get_fp_or_404(fid: str, db: Session) -> QueryFingerprint:
    fp = db.query(QueryFingerprint).filter_by(id=fid).first()
    if not fp:
        raise HTTPException(status_code=404, detail="query not found")
    return fp


@router.get("", response_model=Page[QuerySummary])
def list_queries(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort: Literal["mean_latency_desc", "calls_desc", "last_seen_desc"] = "mean_latency_desc",
    q: str = Query(default="", description="filter by normalized_query substring"),
    db: Session = Depends(get_db),
):
    # latest metric per fingerprint (subquery)
    latest_metric_sq = (
        db.query(
            QueryMetric.fingerprint_id,
            func.max(QueryMetric.captured_at).label("max_captured"),
        )
        .group_by(QueryMetric.fingerprint_id)
        .subquery()
    )
    latest_metric = (
        db.query(QueryMetric)
        .join(
            latest_metric_sq,
            (QueryMetric.fingerprint_id == latest_metric_sq.c.fingerprint_id)
            & (QueryMetric.captured_at == latest_metric_sq.c.max_captured),
        )
        .subquery()
    )

    reg_count_sq = (
        db.query(
            QueryRegression.fingerprint_id,
            func.count(QueryRegression.id).label("rc"),
        )
        .group_by(QueryRegression.fingerprint_id)
        .subquery()
    )

    base = (
        db.query(
            QueryFingerprint,
            latest_metric.c.mean_exec_time_ms.label("lm"),
            latest_metric.c.calls.label("lc"),
            func.coalesce(reg_count_sq.c.rc, 0).label("rc"),
        )
        .outerjoin(latest_metric, QueryFingerprint.id == latest_metric.c.fingerprint_id)
        .outerjoin(reg_count_sq, QueryFingerprint.id == reg_count_sq.c.fingerprint_id)
    )

    if q:
        base = base.filter(QueryFingerprint.normalized_query.ilike(f"%{q}%"))

    sort_col = {
        "mean_latency_desc": latest_metric.c.mean_exec_time_ms.desc().nulls_last(),
        "calls_desc": latest_metric.c.calls.desc().nulls_last(),
        "last_seen_desc": QueryFingerprint.last_seen_at.desc(),
    }[sort]
    base = base.order_by(sort_col)

    total = base.count()
    rows = base.offset(offset).limit(limit).all()

    items = [
        QuerySummary(
            id=fp.id,
            fingerprint_hash=fp.fingerprint_hash,
            normalized_query=fp.normalized_query,
            last_seen_at=fp.last_seen_at,
            latest_mean_ms=lm,
            latest_calls=lc,
            regression_count=rc,
        )
        for fp, lm, lc, rc in rows
    ]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{fid}", response_model=QueryDetail)
def get_query(fid: UUID, db: Session = Depends(get_db)):
    fp = _get_fp_or_404(str(fid), db)

    latest_m = (
        db.query(QueryMetric)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryMetric.captured_at.desc())
        .first()
    )
    latest_p = (
        db.query(QueryPlan)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )
    reg_count = db.query(QueryRegression).filter_by(fingerprint_id=fp.id).count()

    return QueryDetail(
        fingerprint=FingerprintOut.model_validate(fp),
        latest_metric=MetricPoint.model_validate(latest_m) if latest_m else None,
        latest_plan=PlanSummary.model_validate(latest_p) if latest_p else None,
        regression_count=reg_count,
    )


@router.get("/{fid}/metrics", response_model=list[MetricPoint])
def get_metrics(
    fid: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    _get_fp_or_404(str(fid), db)
    rows = (
        db.query(QueryMetric)
        .filter_by(fingerprint_id=str(fid))
        .order_by(QueryMetric.captured_at.asc())
        .limit(limit)
        .all()
    )
    return [MetricPoint.model_validate(r) for r in rows]


@router.get("/{fid}/plans", response_model=list[PlanSummary])
def get_plans(
    fid: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    _get_fp_or_404(str(fid), db)
    rows = (
        db.query(QueryPlan)
        .filter_by(fingerprint_id=str(fid))
        .order_by(QueryPlan.captured_at.desc())
        .limit(limit)
        .all()
    )
    return [PlanSummary.model_validate(r) for r in rows]


@router.get("/{fid}/plans/latest", response_model=PlanDetail)
def get_latest_plan(fid: UUID, db: Session = Depends(get_db)):
    _get_fp_or_404(str(fid), db)
    plan = (
        db.query(QueryPlan)
        .filter_by(fingerprint_id=str(fid))
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )
    if not plan:
        raise HTTPException(status_code=404, detail="no plan captured yet")
    return PlanDetail.model_validate(plan)


@router.get("/{fid}/recommendations", response_model=RecommendationList)
def get_query_recommendations(fid: UUID, db: Session = Depends(get_db)):
    fp = _get_fp_or_404(str(fid), db)
    latest_metric = (
        db.query(QueryMetric)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryMetric.captured_at.desc())
        .first()
    )
    latest_plan = (
        db.query(QueryPlan)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )
    latest_regression = (
        db.query(QueryRegression)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryRegression.created_at.desc())
        .first()
    )

    items = recommend_for_query(
        normalized_query=fp.normalized_query,
        latest_metric=latest_metric,
        latest_plan=latest_plan,
        regression_type=latest_regression.regression_type if latest_regression else None,
    )
    return RecommendationList(items=[RecommendationOut.model_validate(item.to_dict()) for item in items])


@router.get("/{fid}/agent-report", response_model=AgentReport)
def get_query_agent_report(fid: UUID, db: Session = Depends(get_db)):
    fp = _get_fp_or_404(str(fid), db)
    latest_metric = (
        db.query(QueryMetric)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryMetric.captured_at.desc())
        .first()
    )
    latest_plan = (
        db.query(QueryPlan)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryPlan.captured_at.desc())
        .first()
    )
    latest_regression = (
        db.query(QueryRegression)
        .filter_by(fingerprint_id=fp.id)
        .order_by(QueryRegression.created_at.desc())
        .first()
    )
    report = build_performance_agent_report(
        normalized_query=fp.normalized_query,
        latest_metric=latest_metric,
        latest_plan=latest_plan,
        latest_regression=latest_regression,
    )
    return AgentReport.model_validate(report)
