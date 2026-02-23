"""Tests for the Attractor convergence agent."""

from __future__ import annotations

import pytest
from dark_factory.attractor.convergence import AttractorEngine
from dark_factory.attractor.models import (
    BudgetAllocation,
    ConvergenceState,
    ConvergeRequest,
    ExecutionMode,
)
from httpx import AsyncClient


def _make_request(**overrides) -> ConvergeRequest:
    defaults = {
        "spec_id": "spec-20260219-auth",
        "spec_version": "1.0.0",
        "spec": {
            "acceptance_criteria": [
                {"criterion": "Valid refresh", "satisfaction_weight": 0.5},
                {"criterion": "Token revocation", "satisfaction_weight": 0.5},
            ]
        },
        "satisfaction_threshold": 0.90,
        "max_iterations": 5,
        "budget": BudgetAllocation(total_budget_usd=10.0),
        "mode": ExecutionMode.AUTONOMOUS,
    }
    defaults.update(overrides)
    return ConvergeRequest(**defaults)


@pytest.mark.asyncio
async def test_convergence_runs() -> None:
    engine = AttractorEngine()
    result = await engine.converge(_make_request())
    assert result.spec_id == "spec-20260219-auth"
    assert result.iterations_completed > 0
    assert result.budget_spent_usd > 0


@pytest.mark.asyncio
async def test_budget_exhaustion() -> None:
    engine = AttractorEngine()
    result = await engine.converge(
        _make_request(
            budget=BudgetAllocation(total_budget_usd=0.5),
            max_iterations=20,
        )
    )
    assert result.state == ConvergenceState.BUDGET_EXHAUSTED


@pytest.mark.asyncio
async def test_iteration_history() -> None:
    engine = AttractorEngine()
    result = await engine.converge(_make_request(max_iterations=3))
    assert len(result.iteration_history) <= 3
    for h in result.iteration_history:
        assert h.iteration > 0
        assert 0.0 <= h.satisfaction_score <= 1.0


@pytest.mark.asyncio
async def test_converge_endpoint(client: AsyncClient) -> None:
    resp = await client.post("/attractor/converge", json=_make_request().model_dump())
    assert resp.status_code == 200
    data = resp.json()
    assert data["spec_id"] == "spec-20260219-auth"
    assert data["iterations_completed"] > 0


@pytest.mark.asyncio
async def test_status_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/attractor/status/spec-nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "initializing"
