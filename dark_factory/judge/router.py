"""Judge-01 Scenario Eval router — POST /evaluate."""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, HTTPException

from dark_factory.judge.backends import (
    JudgeBackend,
    SageMakerBackend,
    StubBackend,
)
from dark_factory.judge.models import EvaluateRequest, EvaluateResponse

logger = structlog.get_logger()

router = APIRouter(tags=["judge"])

_backend: JudgeBackend | None = None


def _get_backend() -> JudgeBackend:
    global _backend
    if _backend is not None:
        return _backend

    mode = os.environ.get("JUDGE_BACKEND_MODE", "stub").lower()
    logger.info("judge.backend.init", mode=mode)

    if mode == "sagemaker":
        endpoint = os.environ.get("SAGEMAKER_ENDPOINT_NAME", "")
        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        if not endpoint:
            raise RuntimeError("SAGEMAKER_ENDPOINT_NAME is required when JUDGE_BACKEND_MODE=sagemaker")
        _backend = SageMakerBackend(endpoint_name=endpoint, region=region)

    elif mode == "stub":
        _backend = StubBackend()

    else:
        raise RuntimeError(
            f"Unknown JUDGE_BACKEND_MODE: {mode!r}. "
            "Only 'sagemaker' (D3N model) and 'stub' (testing) are supported. "
            "LLMs are never used as backends — only trained D3N models."
        )

    return _backend


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(request: EvaluateRequest) -> EvaluateResponse:
    """Evaluate a scenario trajectory against a satisfaction criterion.

    This endpoint is called by SDSM when it forwards
    POST /api/dark-factory/evaluate requests.
    """
    backend = _get_backend()
    try:
        result = await backend.evaluate(request)
        logger.info("judge.evaluate.ok", score=result.score, mode=type(backend).__name__)
        return result
    except Exception:
        logger.exception("judge.evaluate.error")
        raise HTTPException(status_code=502, detail="Judge backend evaluation failed")
