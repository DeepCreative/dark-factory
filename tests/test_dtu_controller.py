"""Tests for the DTU Controller."""

from __future__ import annotations

import pytest
from dark_factory.dtu_controller.models import EnvironmentSpec, TwinStatus
from dark_factory.dtu_controller.orchestrator import DTUOrchestrator
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_provision_environment() -> None:
    orchestrator = DTUOrchestrator(k8s_enabled=False)
    spec = EnvironmentSpec(twins=["persona", "carousel"], scenario_id="scn-test")
    result = await orchestrator.provision(spec)
    assert result.namespace.startswith("dtu-")
    assert len(result.twins) == 2
    assert all(t.status == TwinStatus.READY for t in result.twins)


@pytest.mark.asyncio
async def test_teardown_environment() -> None:
    orchestrator = DTUOrchestrator(k8s_enabled=False)
    spec = EnvironmentSpec(twins=["persona"])
    prov = await orchestrator.provision(spec)
    result = await orchestrator.teardown(prov.namespace)
    assert result.status == "terminated"

    status = await orchestrator.status(prov.namespace)
    assert status is None


@pytest.mark.asyncio
async def test_unknown_twin_skipped() -> None:
    orchestrator = DTUOrchestrator(k8s_enabled=False)
    spec = EnvironmentSpec(twins=["persona", "nonexistent-service"])
    result = await orchestrator.provision(spec)
    assert len(result.twins) == 1


@pytest.mark.asyncio
async def test_list_environments() -> None:
    orchestrator = DTUOrchestrator(k8s_enabled=False)
    await orchestrator.provision(EnvironmentSpec(twins=["persona"]))
    await orchestrator.provision(EnvironmentSpec(twins=["redis"]))
    envs = await orchestrator.list_environments()
    assert len(envs) >= 2


@pytest.mark.asyncio
async def test_provision_endpoint(client: AsyncClient) -> None:
    resp = await client.post(
        "/dtu/provision",
        json={"environment": {"twins": ["persona", "postgresql"], "scenario_id": "scn-1"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["namespace"].startswith("dtu-")
    assert len(data["twins"]) == 2


@pytest.mark.asyncio
async def test_environments_list_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/dtu/environments")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_teardown_endpoint(client: AsyncClient) -> None:
    prov = await client.post(
        "/dtu/provision",
        json={"environment": {"twins": ["redis"]}},
    )
    ns = prov.json()["namespace"]
    resp = await client.post("/dtu/teardown", json={"namespace": ns})
    assert resp.status_code == 200
    assert resp.json()["status"] == "terminated"
