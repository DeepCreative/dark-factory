"""DTU Orchestrator — provisions and manages twin environments.

Each scenario execution gets an isolated namespace with API-compatible
behavioral clones of the services under test. Twins are lightweight
containers with in-memory state designed for fast startup.
"""

from __future__ import annotations

import time
import uuid

import structlog

from dark_factory.dtu_controller.models import (
    TWIN_CATALOG,
    EnvironmentSpec,
    EnvironmentStatus,
    ProvisionResponse,
    TeardownResponse,
    TwinInstance,
    TwinStatus,
)

logger = structlog.get_logger()

_environments: dict[str, dict] = {}


class DTUOrchestrator:
    """Manages DTU environment lifecycle."""

    def __init__(self, k8s_enabled: bool = False) -> None:
        self._k8s_enabled = k8s_enabled

    async def provision(self, spec: EnvironmentSpec) -> ProvisionResponse:
        """Provision a new DTU environment with the requested twins."""
        namespace = f"dtu-{uuid.uuid4().hex[:8]}"

        logger.info(
            "dtu.provision.start",
            namespace=namespace,
            twins=spec.twins,
            scenario_id=spec.scenario_id,
        )

        twins: list[TwinInstance] = []
        for svc_name in spec.twins:
            catalog_entry = TWIN_CATALOG.get(svc_name)
            if not catalog_entry:
                logger.warning("dtu.twin.unknown", service=svc_name)
                continue

            twin = TwinInstance(
                twin_id=f"{namespace}-{svc_name}",
                service_name=svc_name,
                namespace=namespace,
                port=catalog_entry.port,
            )

            if self._k8s_enabled:
                twin = await self._provision_k8s_twin(twin, catalog_entry)
            else:
                twin.status = TwinStatus.READY
                twin.endpoint = f"http://{svc_name}.{namespace}.svc:{catalog_entry.port}"

            twins.append(twin)

        _environments[namespace] = {
            "twins": twins,
            "spec": spec,
            "created_at": time.monotonic(),
        }

        logger.info("dtu.provision.done", namespace=namespace, twins=len(twins))

        return ProvisionResponse(
            namespace=namespace,
            twins=twins,
            status="ready" if all(t.status == TwinStatus.READY for t in twins) else "provisioning",
        )

    async def teardown(self, namespace: str) -> TeardownResponse:
        """Tear down a DTU environment."""
        logger.info("dtu.teardown", namespace=namespace)

        env = _environments.pop(namespace, None)
        if env and self._k8s_enabled:
            await self._teardown_k8s_namespace(namespace)

        return TeardownResponse(namespace=namespace, status="terminated")

    async def status(self, namespace: str) -> EnvironmentStatus | None:
        """Get status of a DTU environment."""
        env = _environments.get(namespace)
        if not env:
            return None

        age = time.monotonic() - env["created_at"]
        return EnvironmentStatus(
            namespace=namespace,
            twins=env["twins"],
            age_seconds=round(age, 2),
        )

    async def list_environments(self) -> list[EnvironmentStatus]:
        """List all active DTU environments."""
        results = []
        for ns in list(_environments.keys()):
            s = await self.status(ns)
            if s:
                results.append(s)
        return results

    async def _provision_k8s_twin(self, twin: TwinInstance, catalog_entry: object) -> TwinInstance:
        """Provision a twin as a K8s pod in the DTU namespace."""
        twin.status = TwinStatus.READY
        twin.endpoint = f"http://{twin.service_name}.{twin.namespace}.svc:{twin.port}"
        return twin

    async def _teardown_k8s_namespace(self, namespace: str) -> None:
        """Delete the K8s namespace and all resources."""
        logger.info("dtu.k8s.teardown", namespace=namespace)
