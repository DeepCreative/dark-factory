"""Pydantic models for the DTU Controller."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TwinStatus(str, Enum):  # noqa: UP042
    PENDING = "pending"
    PROVISIONING = "provisioning"
    READY = "ready"
    RUNNING = "running"
    TEARING_DOWN = "tearing_down"
    TERMINATED = "terminated"
    ERROR = "error"


class TwinSpec(BaseModel):
    """Specification for a single service twin."""

    service_name: str
    source_openapi_url: str | None = None
    image: str | None = None
    port: int = 8080
    env: dict[str, str] = Field(default_factory=dict)
    readiness_path: str = "/health"


TWIN_CATALOG: dict[str, TwinSpec] = {
    "persona": TwinSpec(service_name="persona", port=8080, readiness_path="/health"),
    "carousel": TwinSpec(service_name="carousel", port=8081, readiness_path="/health"),
    "sdsm": TwinSpec(service_name="sdsm", port=8082, readiness_path="/health"),
    "alexandria": TwinSpec(service_name="alexandria", port=8083, readiness_path="/health"),
    "postgresql": TwinSpec(service_name="postgresql", port=5432, readiness_path=""),
    "redis": TwinSpec(service_name="redis", port=6379, readiness_path=""),
}


class TwinInstance(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    twin_id: str
    service_name: str
    namespace: str
    status: TwinStatus = TwinStatus.PENDING
    endpoint: str | None = None
    port: int = 8080


class EnvironmentSpec(BaseModel):
    """Specification for a DTU environment (collection of twins)."""

    twins: list[str] = Field(default_factory=list, description="Service names from twin catalog")
    scenario_id: str | None = None
    ttl_seconds: int = 600


class ProvisionRequest(BaseModel):
    environment: EnvironmentSpec


class ProvisionResponse(BaseModel):
    namespace: str
    twins: list[TwinInstance]
    status: str = "provisioning"


class TeardownRequest(BaseModel):
    namespace: str


class TeardownResponse(BaseModel):
    namespace: str
    status: str = "terminated"


class EnvironmentStatus(BaseModel):
    namespace: str
    twins: list[TwinInstance]
    age_seconds: float = 0.0
