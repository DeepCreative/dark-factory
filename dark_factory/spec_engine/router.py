"""Spec Engine API routes."""

from __future__ import annotations

import structlog
from fastapi import APIRouter

from dark_factory.spec_engine.compiler import compile_spec
from dark_factory.spec_engine.models import (
    CompileRequest,
    CompileResponse,
    ValidateRequest,
    ValidateResponse,
)
from dark_factory.spec_engine.validator import validate_spec

logger = structlog.get_logger()

router = APIRouter(prefix="/specs", tags=["spec-engine"])


@router.post("/validate", response_model=ValidateResponse)
async def validate(request: ValidateRequest) -> ValidateResponse:
    """Validate a spec for completeness and correctness."""
    result = validate_spec(request.spec)
    logger.info("spec_engine.validate", spec_id=request.spec.id, valid=result.valid, errors=len(result.errors))
    return result


@router.post("/compile", response_model=CompileResponse)
async def compile(request: CompileRequest) -> CompileResponse:
    """Compile a published spec into scenario skeletons."""
    validation = validate_spec(request.spec)
    if not validation.valid:
        return CompileResponse(
            spec_id=request.spec.id,
            version=request.spec.version,
            scenarios=[],
            errors=validation.errors,
        )

    result = compile_spec(request.spec)
    logger.info(
        "spec_engine.compile",
        spec_id=request.spec.id,
        scenarios=len(result.scenarios),
        errors=len(result.errors),
    )
    return result
