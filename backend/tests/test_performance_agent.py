from __future__ import annotations

from types import SimpleNamespace

from app.core.performance_agent import build_performance_agent_report


def test_performance_agent_reports_seq_scan_and_temp_spill():
    metric = SimpleNamespace(rows_returned=2500, temp_blks_written=7)
    plan = SimpleNamespace(uses_seq_scan=True, actual_rows=1200, estimated_rows=80)
    regression = SimpleNamespace(regression_type="latency_spike", severity="medium")

    report = build_performance_agent_report(
        normalized_query="SELECT * FROM events WHERE user_id = $1",
        latest_metric=metric,
        latest_plan=plan,
        latest_regression=regression,
    )

    assert report["recommendation"]["id"] == "seq-scan-index-suggestion"
    assert report["safe_sql"] is None
    assert report["confidence"] <= 0.7
    assert len(report["trace"]) == 5


def test_performance_agent_handles_missing_evidence():
    report = build_performance_agent_report(
        normalized_query="SELECT 1",
        latest_metric=None,
        latest_plan=None,
        latest_regression=None,
    )

    assert report["recommendation"] is None
    assert report["safe_sql"] is None
    assert report["safety_warnings"]
    assert len(report["trace"]) == 5
