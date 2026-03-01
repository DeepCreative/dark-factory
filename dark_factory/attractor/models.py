"""Pydantic models for the Attractor convergence agent."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConvergenceState(str, Enum):  # noqa: UP042
    INITIALIZING = "initializing"
    GENERATING = "generating"
    VERIFYING = "verifying"
    EVALUATING = "evaluating"
    REGENERATING = "regenerating"
    CONVERGED = "converged"
    STALLED = "stalled"
    BUDGET_EXHAUSTED = "budget_exhausted"
    AMENDMENT_PROPOSED = "amendment_proposed"


class ExecutionMode(str, Enum):  # noqa: UP042
    AUTONOMOUS = "autonomous"
    SUPERVISED = "supervised"
    DEBUG = "debug"
    BENCHMARK = "benchmark"


class AmendmentDiagnosis(str, Enum):  # noqa: UP042
    AMBIGUOUS = "ambiguous"
    CONTRADICTORY = "contradictory"
    UNSATISFIABLE = "unsatisfiable"
    UNDERSPECIFIED = "underspecified"


class BudgetAllocation(BaseModel):
    generation_pct: float = 0.50
    scenarios_pct: float = 0.30
    judge_pct: float = 0.15
    overhead_pct: float = 0.05
    total_budget_usd: float = 100.0

    @property
    def generation_budget(self) -> float:
        return self.total_budget_usd * self.generation_pct

    @property
    def scenarios_budget(self) -> float:
        return self.total_budget_usd * self.scenarios_pct

    @property
    def judge_budget(self) -> float:
        return self.total_budget_usd * self.judge_pct


class AmendmentProposal(BaseModel):
    """Proposal to amend a spec criterion that appears unsatisfiable."""

    criterion_ref: str
    current_score: float
    iterations_stuck: int
    diagnosis: AmendmentDiagnosis
    suggestion: str


class CodebaseContext(BaseModel):
    """Discovered codebase context for a target service.

    Built by the Attractor before generation so Codex-01 has awareness
    of existing code, interfaces, and test patterns.
    """

    service_name: str
    discovered_files: list[str] = Field(default_factory=list)
    interface_files: list[str] = Field(default_factory=list)
    test_patterns: list[str] = Field(default_factory=list)
    existing_dependencies: list[str] = Field(default_factory=list)


class IterationResult(BaseModel):
    iteration: int
    satisfaction_score: float
    delta: float = 0.0
    criteria_scores: dict[str, float] = Field(default_factory=dict)
    budget_spent_usd: float = 0.0
    stall_count: int = 0


class ConvergeRequest(BaseModel):
    spec_id: str
    spec_version: str
    spec: dict[str, Any]
    satisfaction_threshold: float = 0.90
    max_iterations: int = 20
    budget: BudgetAllocation = Field(default_factory=BudgetAllocation)
    mode: ExecutionMode = ExecutionMode.AUTONOMOUS
    stall_limit: int = 3


class ConvergeResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    spec_id: str
    state: ConvergenceState
    iterations_completed: int
    final_satisfaction: float
    iteration_history: list[IterationResult] = Field(default_factory=list)
    budget_spent_usd: float = 0.0
    code_artifact_ref: str | None = None
    amendments: list[AmendmentProposal] = Field(default_factory=list)
    error: str | None = None


class ConvergenceStatus(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    spec_id: str
    state: ConvergenceState
    current_iteration: int
    current_satisfaction: float
    budget_remaining_usd: float
