"""Pydantic models for the Spec Engine."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SpecState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    ACTIVE = "active"
    SATISFIED = "satisfied"
    DEPRECATED = "deprecated"


class AcceptanceCriterion(BaseModel):
    criterion: str
    priority: str = "P1"
    satisfaction_weight: float = Field(ge=0.0, le=1.0)


class SpecDomain(BaseModel):
    service: str
    language: str
    framework: str | None = None


class SpecInput(BaseModel):
    name: str
    type: str
    format: str | None = None
    description: str | None = None


class SpecOutput(BaseModel):
    name: str
    type: str
    format: str | None = None
    constraints: list[str] = Field(default_factory=list)


class SpecDependencies(BaseModel):
    services: list[str] = Field(default_factory=list)
    d3n_capabilities: list[str] = Field(default_factory=list)


class Spec(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: str = Field(..., description="Globally unique spec ID, format: spec-{date}-{slug}")
    version: str = Field(..., description="Semantic version")
    name: str
    description: str
    state: SpecState = SpecState.DRAFT
    domain: SpecDomain
    inputs: list[SpecInput] = Field(default_factory=list)
    outputs: list[SpecOutput] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    dependencies: SpecDependencies = Field(default_factory=SpecDependencies)


class ScenarioStep(BaseModel):
    actor: str
    action: str
    expect: str


class ScenarioSkeleton(BaseModel):
    """Compiled scenario skeleton from a spec's acceptance criteria."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    spec_ref: str
    criterion_ref: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[ScenarioStep] = Field(default_factory=list)
    satisfaction_criteria: str = ""


class CompileRequest(BaseModel):
    spec: Spec


class CompileResponse(BaseModel):
    spec_id: str
    version: str
    scenarios: list[ScenarioSkeleton]
    errors: list[str] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    spec: Spec


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
