"""Tests for the Scenario Executor."""

from __future__ import annotations

import pytest
from dark_factory.scenario_executor.executor import ScenarioExecutor
from dark_factory.scenario_executor.models import ExecuteRequest, ScenarioStatus
from httpx import AsyncClient


def _make_request(**overrides) -> ExecuteRequest:
    defaults = {
        "scenario_id": "scn-test-001",
        "spec_ref": "spec-20260219-auth:v1.0.0",
        "criterion_ref": "Valid refresh produces new token pair",
        "steps": [
            {"actor": "client", "action": "POST /oauth/token", "expect": "200 OK"},
            {"actor": "system", "action": "Generate new token", "expect": "Token returned"},
        ],
        "satisfaction_criteria": "Valid refresh produces new token pair",
    }
    defaults.update(overrides)
    return ExecuteRequest(**defaults)


@pytest.mark.asyncio
async def test_executor_stub_mode() -> None:
    executor = ScenarioExecutor()
    result = await executor.execute(_make_request())
    assert result.status == ScenarioStatus.COMPLETED
    assert result.trajectory is not None
    assert len(result.trajectory.steps) == 2
    assert all(s.assertions_passed for s in result.trajectory.steps)


@pytest.mark.asyncio
async def test_executor_empty_steps() -> None:
    executor = ScenarioExecutor()
    result = await executor.execute(_make_request(steps=[]))
    assert result.status == ScenarioStatus.COMPLETED
    assert result.trajectory is not None
    assert len(result.trajectory.steps) == 0


@pytest.mark.asyncio
async def test_executor_batch() -> None:
    executor = ScenarioExecutor()
    requests = [_make_request(scenario_id=f"scn-batch-{i}") for i in range(3)]
    results = await executor.execute_batch(requests, max_concurrency=2)
    assert len(results) == 3
    assert all(r.status == ScenarioStatus.COMPLETED for r in results)


@pytest.mark.asyncio
async def test_execute_endpoint(client: AsyncClient) -> None:
    resp = await client.post("/scenarios/execute", json=_make_request().model_dump())
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["trajectory"]["steps"]


@pytest.mark.asyncio
async def test_batch_endpoint(client: AsyncClient) -> None:
    requests = [_make_request(scenario_id=f"scn-{i}").model_dump() for i in range(2)]
    resp = await client.post(
        "/scenarios/execute-batch",
        json={"scenarios": requests, "parallel": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 2
