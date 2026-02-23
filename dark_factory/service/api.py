"""Dark Factory FastAPI application."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response

from dark_factory import __version__
from dark_factory.attractor.router import router as attractor_router
from dark_factory.dtu_controller.router import router as dtu_router
from dark_factory.judge.router import router as judge_router
from dark_factory.scenario_executor.router import router as scenario_router
from dark_factory.spec_engine.router import router as spec_router

logger = structlog.get_logger()

_start_time: float = 0.0


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global _start_time
    _start_time = time.monotonic()
    logger.info("dark-factory.startup", version=__version__)
    yield
    logger.info("dark-factory.shutdown")


app = FastAPI(
    title="Dark Factory",
    version=__version__,
    lifespan=lifespan,
)

app.include_router(judge_router)
app.include_router(spec_router)
app.include_router(scenario_router)
app.include_router(attractor_router)
app.include_router(dtu_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/ready")
async def ready() -> dict:
    return {"status": "ready", "uptime_seconds": round(time.monotonic() - _start_time, 2)}


@app.middleware("http")
async def request_logging(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
    start = time.monotonic()
    response: Response = await call_next(request)
    elapsed = round((time.monotonic() - start) * 1000, 2)
    logger.info(
        "http.request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        elapsed_ms=elapsed,
    )
    return response
