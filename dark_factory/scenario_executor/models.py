"""Pydantic models for the Scenario Executor."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScenarioStatus(str, Enum):  # noqa: UP042
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class StepResult(BaseModel):
    step_id: str
    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] = Field(default_factory=dict)
    assertions_passed: bool = False
    latency_ms: float = 0.0
    error: str | None = None


class TrajectoryLog(BaseModel):
    trajectory_id: str
    scenario_id: str
    steps: list[StepResult] = Field(default_factory=list)
    structural_assertions: dict[str, int] = Field(default_factory=dict)
    timing_assertions: dict[str, Any] = Field(default_factory=dict)


class ExecuteRequest(BaseModel):
    """Request to execute a scenario skeleton against a DTU environment."""

    scenario_id: str
    spec_ref: str
    criterion_ref: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[dict[str, str]] = Field(default_factory=list)
    satisfaction_criteria: str = ""
    dtu_namespace: str | None = None
    timeout_seconds: int = 300


class ExecuteResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    scenario_id: str
    status: ScenarioStatus
    trajectory: TrajectoryLog | None = None
    satisfaction_score: float | None = None
    judge_reasoning: str | None = None
    error: str | None = None
    elapsed_ms: float = 0.0


class BatchExecuteRequest(BaseModel):
    scenarios: list[ExecuteRequest]
    parallel: bool = True
    max_concurrency: int = 5


class BatchExecuteResponse(BaseModel):
    results: list[ExecuteResponse]
    aggregate_satisfaction: float | None = None
    total_elapsed_ms: float = 0.0
