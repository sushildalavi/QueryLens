"""Smoke tests for the FastAPI app using TestClient (no external DB needed
for basic route shape tests; DB-backed tests use the integration container)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(test_engine, db_url):
    """Create a TestClient that uses the integration Postgres container."""
    os.environ["DATABASE_URL"] = db_url

    # Re-import settings so it picks up the new DATABASE_URL
    import app.config as cfg_mod

    cfg_mod.settings = cfg_mod.Settings()

    # Override engine and SessionLocal in database module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import app.database as db_mod

    db_mod.engine = create_engine(db_url, pool_pre_ping=True, future=True)
    db_mod.SessionLocal = sessionmaker(bind=db_mod.engine, autoflush=False, expire_on_commit=False)

    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"


def test_queries_list_empty(client):
    r = client.get("/api/queries")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_regressions_list_empty(client):
    r = client.get("/api/regressions")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_query_not_found(client):
    r = client.get("/api/queries/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_regression_not_found(client):
    r = client.get("/api/regressions/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_collect_run(client):
    r = client.post("/api/collect/run")
    assert r.status_code == 200
    data = r.json()
    assert "fingerprints" in data
    assert "regressions" in data
    assert "diagnostics" in data
    assert "duration_ms" in data


def test_placement_simulate(client):
    r = client.post("/api/placement/simulate", json={"seed": 7, "tenants": 12, "regions": 2, "clusters_per_region": 1, "nodes_per_cluster": 2})
    assert r.status_code == 200
    data = r.json()
    assert "algorithms" in data
    assert data["algorithms"]


def test_query_diagnostics_route_shape(client):
    r = client.get("/api/queries/00000000-0000-0000-0000-000000000000/diagnostics")
    assert r.status_code == 404


def test_docs_available(client):
    r = client.get("/docs")
    assert r.status_code == 200
