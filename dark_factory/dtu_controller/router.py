"""DTU Controller API routes."""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, HTTPException

from dark_factory.dtu_controller.models import (
    EnvironmentStatus,
    ProvisionRequest,
    ProvisionResponse,
    TeardownRequest,
    TeardownResponse,
)
from dark_factory.dtu_controller.orchestrator import DTUOrchestrator

logger = structlog.get_logger()

router = APIRouter(prefix="/dtu", tags=["dtu-controller"])

_orchestrator: DTUOrchestrator | None = None


def _get_orchestrator() -> DTUOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        k8s_enabled = os.environ.get("DTU_K8S_ENABLED", "false").lower() == "true"
        _orchestrator = DTUOrchestrator(k8s_enabled=k8s_enabled)
    return _orchestrator


@router.post("/provision", response_model=ProvisionResponse)
async def provision(request: ProvisionRequest) -> ProvisionResponse:
    """Provision a new DTU environment with service twins."""
    orchestrator = _get_orchestrator()
    return await orchestrator.provision(request.environment)


@router.post("/teardown", response_model=TeardownResponse)
async def teardown(request: TeardownRequest) -> TeardownResponse:
    """Tear down a DTU environment."""
    orchestrator = _get_orchestrator()
    return await orchestrator.teardown(request.namespace)


@router.get("/environments", response_model=list[EnvironmentStatus])
async def list_environments() -> list[EnvironmentStatus]:
    """List all active DTU environments."""
    orchestrator = _get_orchestrator()
    return await orchestrator.list_environments()


@router.get("/environments/{namespace}", response_model=EnvironmentStatus)
async def environment_status(namespace: str) -> EnvironmentStatus:
    """Get status of a specific DTU environment."""
    orchestrator = _get_orchestrator()
    status = await orchestrator.status(namespace)
    if not status:
        raise HTTPException(status_code=404, detail=f"Environment {namespace} not found")
    return status
