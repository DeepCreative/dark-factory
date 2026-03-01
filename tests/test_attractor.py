"""Tests for the Attractor convergence agent."""

from __future__ import annotations

import pytest
from dark_factory.attractor.convergence import AttractorEngine
from dark_factory.attractor.models import (
    AmendmentDiagnosis,
    BudgetAllocation,
    ConvergenceState,
    ConvergeRequest,
    ExecutionMode,
    IterationResult,
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


# ---------- amendment detection ----------


def test_detect_amendment_candidates_flags_low_criterion() -> None:
    """Criteria consistently < 0.3 while others > 0.7 produce amendments."""
    engine = AttractorEngine()
    history = [
        IterationResult(
            iteration=i,
            satisfaction_score=0.5,
            criteria_scores={"good_crit": 0.85, "bad_crit": 0.1},
        )
        for i in range(1, 4)
    ]
    amendments = engine._detect_amendment_candidates(history, window=3)
    assert len(amendments) == 1
    assert amendments[0].criterion_ref == "bad_crit"
    assert amendments[0].diagnosis in (AmendmentDiagnosis.AMBIGUOUS, AmendmentDiagnosis.UNSATISFIABLE)


def test_detect_amendment_no_flag_when_criteria_uniform() -> None:
    """No amendments when all criteria are uniformly low (problem is generation, not spec)."""
    engine = AttractorEngine()
    history = [
        IterationResult(
            iteration=i,
            satisfaction_score=0.2,
            criteria_scores={"crit_a": 0.2, "crit_b": 0.25},
        )
        for i in range(1, 4)
    ]
    amendments = engine._detect_amendment_candidates(history, window=3)
    assert amendments == []


def test_detect_amendment_no_flag_when_history_too_short() -> None:
    """No amendments when history is shorter than the window."""
    engine = AttractorEngine()
    history = [
        IterationResult(iteration=1, satisfaction_score=0.5, criteria_scores={"a": 0.1, "b": 0.9}),
    ]
    amendments = engine._detect_amendment_candidates(history, window=3)
    assert amendments == []


@pytest.mark.asyncio
async def test_amendment_proposed_in_supervised_mode() -> None:
    """Supervised mode returns AMENDMENT_PROPOSED when criteria diverge."""

    class StubbedEngine(AttractorEngine):
        async def _generate(self, spec, iteration, *, context=None):
            return 0.10

        async def _verify(self, spec_id):
            return 0.05

        async def _evaluate(self, spec_id, spec):
            return 0.45, {"good": 0.85, "bad": 0.05}, 0.05

    engine = StubbedEngine()
    result = await engine.converge(
        _make_request(
            mode=ExecutionMode.SUPERVISED,
            stall_limit=2,
            max_iterations=10,
            satisfaction_threshold=0.95,
        )
    )
    assert result.state == ConvergenceState.AMENDMENT_PROPOSED
    assert len(result.amendments) == 1
    assert result.amendments[0].criterion_ref == "bad"


@pytest.mark.asyncio
async def test_amendment_logged_in_autonomous_mode() -> None:
    """Autonomous mode logs amendments but continues with strategic regeneration."""

    class StubbedEngine(AttractorEngine):
        async def _generate(self, spec, iteration, *, context=None):
            return 0.10

        async def _verify(self, spec_id):
            return 0.05

        async def _evaluate(self, spec_id, spec):
            return 0.45, {"good": 0.85, "bad": 0.05}, 0.05

    engine = StubbedEngine()
    result = await engine.converge(
        _make_request(
            mode=ExecutionMode.AUTONOMOUS,
            stall_limit=2,
            max_iterations=10,
            budget=BudgetAllocation(total_budget_usd=5.0),
        )
    )
    # Should NOT be AMENDMENT_PROPOSED — autonomous mode continues
    assert result.state != ConvergenceState.AMENDMENT_PROPOSED
