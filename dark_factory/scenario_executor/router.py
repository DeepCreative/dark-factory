"""Scenario Executor API routes."""

from __future__ import annotations

import os
import time

import structlog
from fastapi import APIRouter

from dark_factory.scenario_executor.executor import ScenarioExecutor
from dark_factory.scenario_executor.models import (
    BatchExecuteRequest,
    BatchExecuteResponse,
    ExecuteRequest,
    ExecuteResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/scenarios", tags=["scenario-executor"])

_executor: ScenarioExecutor | None = None


def _get_executor() -> ScenarioExecutor:
    global _executor
    if _executor is None:
        _executor = ScenarioExecutor(
            dtu_base_url=os.environ.get("DTU_BASE_URL", ""),
            judge_url=os.environ.get("JUDGE_URL", ""),
        )
    return _executor


@router.post("/execute", response_model=ExecuteResponse)
async def execute_scenario(request: ExecuteRequest) -> ExecuteResponse:
    """Execute a single scenario against a DTU environment."""
    executor = _get_executor()
    return await executor.execute(request)


@router.post("/execute-batch", response_model=BatchExecuteResponse)
async def execute_batch(request: BatchExecuteRequest) -> BatchExecuteResponse:
    """Execute multiple scenarios with bounded concurrency."""
    executor = _get_executor()
    start = time.monotonic()

    results = await executor.execute_batch(
        request.scenarios,
        max_concurrency=request.max_concurrency,
    )

    scores = [r.satisfaction_score for r in results if r.satisfaction_score is not None]
    aggregate = sum(scores) / len(scores) if scores else None
    elapsed = round((time.monotonic() - start) * 1000, 2)

    logger.info(
        "scenario.batch.done",
        total=len(results),
        aggregate_satisfaction=aggregate,
        elapsed_ms=elapsed,
    )

    return BatchExecuteResponse(
        results=results,
        aggregate_satisfaction=aggregate,
        total_elapsed_ms=elapsed,
    )
