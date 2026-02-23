"""Spec-to-Scenario compiler.

Transforms published specs into scenario skeletons that the Scenario Executor
populates with concrete test data. Compilation rules follow spec-engine-prd.md.
"""

from __future__ import annotations

import uuid

import structlog

from dark_factory.spec_engine.models import (
    AcceptanceCriterion,
    CompileResponse,
    ScenarioSkeleton,
    ScenarioStep,
    Spec,
    SpecState,
)

logger = structlog.get_logger()


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def compile_criterion(spec: Spec, criterion: AcceptanceCriterion) -> ScenarioSkeleton:
    """Compile a single acceptance criterion into a scenario skeleton."""
    steps: list[ScenarioStep] = []
    for inp in spec.inputs:
        steps.append(
            ScenarioStep(
                actor="client",
                action=f"Provide {inp.name} ({inp.type})",
                expect=f"{inp.name} accepted by {spec.domain.service}",
            )
        )

    for out in spec.outputs:
        constraint_text = "; ".join(out.constraints) if out.constraints else "valid output"
        steps.append(
            ScenarioStep(
                actor="system",
                action=f"Produce {out.name} ({out.type})",
                expect=constraint_text,
            )
        )

    if not steps:
        steps.append(
            ScenarioStep(
                actor="client",
                action=f"Exercise behavior: {criterion.criterion[:120]}",
                expect="Criterion satisfied",
            )
        )

    return ScenarioSkeleton(
        id=f"scn-{_uid()}",
        spec_ref=f"{spec.id}:{spec.version}",
        criterion_ref=criterion.criterion,
        preconditions=[f"Service {spec.domain.service} is running", f"DTU twin for {spec.domain.service} is available"],
        steps=steps,
        satisfaction_criteria=criterion.criterion,
    )


def compile_invariant(spec: Spec, invariant: str) -> ScenarioSkeleton:
    """Compile an invariant into a negative-test scenario skeleton."""
    return ScenarioSkeleton(
        id=f"scn-inv-{_uid()}",
        spec_ref=f"{spec.id}:{spec.version}",
        criterion_ref=f"[INVARIANT] {invariant}",
        preconditions=[f"Service {spec.domain.service} is running"],
        steps=[
            ScenarioStep(
                actor="adversary",
                action=f"Attempt to violate: {invariant[:200]}",
                expect="System prevents violation",
            ),
            ScenarioStep(
                actor="observer",
                action="Verify invariant still holds",
                expect=f"Invariant maintained: {invariant[:200]}",
            ),
        ],
        satisfaction_criteria=f"System preserves invariant: {invariant}",
    )


def compile_spec(spec: Spec) -> CompileResponse:
    """Compile a full spec into scenario skeletons."""
    errors: list[str] = []

    if spec.state not in (SpecState.PUBLISHED, SpecState.ACTIVE):
        errors.append(f"Spec must be Published or Active to compile; current state: {spec.state}")
        return CompileResponse(spec_id=spec.id, version=spec.version, scenarios=[], errors=errors)

    if not spec.acceptance_criteria:
        errors.append("Spec has no acceptance criteria")

    weights = sum(c.satisfaction_weight for c in spec.acceptance_criteria)
    if spec.acceptance_criteria and abs(weights - 1.0) > 0.01:
        errors.append(f"Acceptance criteria weights sum to {weights:.2f}, expected 1.0")

    if errors:
        return CompileResponse(spec_id=spec.id, version=spec.version, scenarios=[], errors=errors)

    scenarios: list[ScenarioSkeleton] = []

    for criterion in spec.acceptance_criteria:
        scenarios.append(compile_criterion(spec, criterion))

    for invariant in spec.invariants:
        scenarios.append(compile_invariant(spec, invariant))

    logger.info(
        "spec_engine.compile",
        spec_id=spec.id,
        version=spec.version,
        scenarios=len(scenarios),
    )

    return CompileResponse(spec_id=spec.id, version=spec.version, scenarios=scenarios)
