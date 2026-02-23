"""Spec validation — ensures specs are well-formed before compilation."""

from __future__ import annotations

import re

from dark_factory.spec_engine.models import Spec, ValidateResponse

SPEC_ID_PATTERN = re.compile(r"^spec-\d{8}-[a-z0-9-]+$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def validate_spec(spec: Spec) -> ValidateResponse:
    """Validate a spec for completeness and correctness."""
    errors: list[str] = []
    warnings: list[str] = []

    if not SPEC_ID_PATTERN.match(spec.id):
        errors.append(f"Spec ID must match 'spec-{{date}}-{{slug}}' format, got: {spec.id}")

    if not SEMVER_PATTERN.match(spec.version):
        errors.append(f"Version must be semver (x.y.z), got: {spec.version}")

    if not spec.description.strip():
        errors.append("Description is required")

    if not spec.acceptance_criteria:
        errors.append("At least one acceptance criterion is required")

    weights = sum(c.satisfaction_weight for c in spec.acceptance_criteria)
    if spec.acceptance_criteria and abs(weights - 1.0) > 0.01:
        errors.append(f"Acceptance criteria weights must sum to 1.0, got {weights:.2f}")

    if not spec.invariants:
        warnings.append("No invariants defined — consider adding safety properties")

    if not spec.inputs:
        warnings.append("No inputs defined")

    if not spec.outputs:
        warnings.append("No outputs defined")

    for dep in spec.dependencies.d3n_capabilities:
        if ":" not in dep:
            errors.append(f"D3N capability must be 'model:capability' format, got: {dep}")

    if not spec.domain.service:
        errors.append("Domain service is required")

    if not spec.domain.language:
        errors.append("Domain language is required")

    return ValidateResponse(valid=len(errors) == 0, errors=errors, warnings=warnings)
