from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.collect import router as collect_router
from app.api.collector_status import router as collector_status_router
from app.api.placement import router as placement_router
from app.api.queries import router as queries_router
from app.api.regressions import router as regressions_router
from app.api.reports import router as reports_router
from app.config import settings
from app.database import engine
from app.observability.metrics import api_request_latency_seconds
from app.streaming.consumer import TelemetryConsumer

log = logging.getLogger(__name__)


consumer = TelemetryConsumer()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await consumer.start()
    try:
        yield
    finally:
        await consumer.stop()


app = FastAPI(
    title="PlanTrace",
    description="SQL query diagnostics and synthetic workload optimization platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(queries_router)
app.include_router(regressions_router)
app.include_router(collect_router)
app.include_router(placement_router)
app.include_router(reports_router)
app.include_router(collector_status_router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception("unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "internal error"})


@app.get("/health", tags=["health"])
def health():
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = str(exc)
    return {"status": "ok", "db": db_status}


@app.middleware("http")
async def track_request_latency(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    dt = time.perf_counter() - t0
    api_request_latency_seconds.labels(
        path=request.url.path, method=request.method, status=str(response.status_code)
    ).observe(dt)
    return response


@app.get("/metrics", tags=["health"])
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
