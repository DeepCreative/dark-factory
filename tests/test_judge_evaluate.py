"""Tests for the Judge-01 Scenario Eval /evaluate endpoint."""

from __future__ import annotations

import pytest
from dark_factory.judge.backends import StubBackend
from dark_factory.judge.models import EvaluateRequest, EvaluateResponse
from httpx import AsyncClient

VALID_PAYLOAD = {
    "prompt": "Evaluate the following trajectory...",
    "trajectory_log": {"steps": [{"action": "click", "target": "button"}]},
    "satisfaction_criterion": "User can submit the form successfully",
}


# ---------- stub backend unit tests ----------


@pytest.mark.asyncio
async def test_stub_backend_returns_fixed_score() -> None:
    backend = StubBackend()
    req = EvaluateRequest(**VALID_PAYLOAD)
    result = await backend.evaluate(req)
    assert result.score == 0.5
    assert result.model_version == "stub-v0"


# ---------- /evaluate endpoint integration (stub mode) ----------


@pytest.mark.asyncio
async def test_evaluate_stub_mode(client: AsyncClient) -> None:
    resp = await client.post("/evaluate", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 0.5
    assert data["model_version"] == "stub-v0"
    assert isinstance(data["reasoning"], str)


@pytest.mark.asyncio
async def test_evaluate_missing_fields(client: AsyncClient) -> None:
    resp = await client.post("/evaluate", json={"prompt": "hello"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_evaluate_response_model() -> None:
    resp = EvaluateResponse(score=0.75, reasoning="good", model_version="v1")
    assert 0.0 <= resp.score <= 1.0
    assert resp.reasoning == "good"


@pytest.mark.asyncio
async def test_evaluate_score_bounds() -> None:
    with pytest.raises(Exception):
        EvaluateResponse(score=1.5, reasoning=None, model_version=None)
    with pytest.raises(Exception):
        EvaluateResponse(score=-0.1, reasoning=None, model_version=None)


# ---------- invalid backend mode ----------


def test_invalid_backend_mode_raises() -> None:
    """Ensure that unsupported modes (including 'llm') are rejected."""
    import os
    from unittest.mock import patch

    from dark_factory.judge import router as router_mod

    router_mod._backend = None

    with patch.dict(os.environ, {"JUDGE_BACKEND_MODE": "llm"}):
        with pytest.raises(RuntimeError, match="Only.*sagemaker.*stub.*supported"):
            router_mod._get_backend()

    router_mod._backend = None
