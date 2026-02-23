"""Attractor convergence agent API routes."""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, BackgroundTasks

from dark_factory.attractor.convergence import AttractorEngine
from dark_factory.attractor.models import (
    ConvergenceState,
    ConvergenceStatus,
    ConvergeRequest,
    ConvergeResponse,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/attractor", tags=["attractor"])

_engine: AttractorEngine | None = None
_active_sessions: dict[str, ConvergeResponse] = {}


def _get_engine() -> AttractorEngine:
    global _engine
    if _engine is None:
        _engine = AttractorEngine(
            scenario_executor_url=os.environ.get("SCENARIO_EXECUTOR_URL", ""),
            judge_url=os.environ.get("JUDGE_URL", ""),
            dtu_url=os.environ.get("DTU_URL", ""),
        )
    return _engine


@router.post("/converge", response_model=ConvergeResponse)
async def converge(request: ConvergeRequest) -> ConvergeResponse:
    """Start a synchronous convergence loop for a spec."""
    engine = _get_engine()
    result = await engine.converge(request)
    _active_sessions[request.spec_id] = result
    return result


@router.post("/converge-async")
async def converge_async(request: ConvergeRequest, background: BackgroundTasks) -> dict:
    """Start an async convergence loop (returns immediately)."""

    async def _run() -> None:
        engine = _get_engine()
        result = await engine.converge(request)
        _active_sessions[request.spec_id] = result

    background.add_task(_run)
    return {"spec_id": request.spec_id, "status": "started"}


@router.get("/status/{spec_id}", response_model=ConvergenceStatus)
async def convergence_status(spec_id: str) -> ConvergenceStatus:
    """Get convergence status for a spec."""
    session = _active_sessions.get(spec_id)
    if not session:
        return ConvergenceStatus(
            spec_id=spec_id,
            state=ConvergenceState.INITIALIZING,
            current_iteration=0,
            current_satisfaction=0.0,
            budget_remaining_usd=0.0,
        )
    return ConvergenceStatus(
        spec_id=spec_id,
        state=session.state,
        current_iteration=session.iterations_completed,
        current_satisfaction=session.final_satisfaction,
        budget_remaining_usd=0.0,
    )
