"""Judge-01 Scenario Eval backend implementations.

Two modes controlled by JUDGE_BACKEND_MODE:
  - "stub"     : deterministic 0.5 for dev/testing
  - "sagemaker": AWS SageMaker endpoint for the trained D3N Judge-01 model

Only D3N models are used in production. LLMs are never used as backends.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import structlog

from dark_factory.judge.models import EvaluateRequest, EvaluateResponse

logger = structlog.get_logger()


class JudgeBackend(ABC):
    @abstractmethod
    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse: ...


class StubBackend(JudgeBackend):
    """Returns a fixed 0.5 score for dev and integration testing."""

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        return EvaluateResponse(
            score=0.5,
            reasoning="stub backend — fixed score for testing",
            model_version="stub-v0",
        )


class SageMakerBackend(JudgeBackend):
    """Invokes the D3N Judge-01 model via AWS SageMaker real-time inference."""

    def __init__(self, endpoint_name: str, region: str = "us-east-1") -> None:
        self._endpoint_name = endpoint_name
        self._region = region
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("sagemaker-runtime", region_name=self._region)
        return self._client

    async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:
        import asyncio

        payload = json.dumps(
            {
                "prompt": request.prompt,
                "trajectory_log": request.trajectory_log,
                "satisfaction_criterion": request.satisfaction_criterion,
            }
        )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._invoke, payload)

        return EvaluateResponse(
            score=float(result.get("score", 0.0)),
            reasoning=result.get("reasoning"),
            model_version=f"d3n:judge-01-scenario-eval:{self._endpoint_name}",
        )

    def _invoke(self, payload: str) -> dict[str, Any]:
        client = self._get_client()
        response = client.invoke_endpoint(
            EndpointName=self._endpoint_name,
            ContentType="application/json",
            Body=payload.encode("utf-8"),
        )
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)
