"""Tests for the Spec Engine."""

from __future__ import annotations

import pytest
from dark_factory.spec_engine.compiler import compile_spec
from dark_factory.spec_engine.models import (
    AcceptanceCriterion,
    Spec,
    SpecDomain,
    SpecInput,
    SpecOutput,
    SpecState,
)
from dark_factory.spec_engine.validator import validate_spec
from httpx import AsyncClient


def _make_spec(**overrides) -> Spec:
    defaults = {
        "id": "spec-20260219-user-auth-refresh",
        "version": "1.0.0",
        "name": "Silent Token Refresh",
        "description": "Refresh expired access tokens silently",
        "state": SpecState.PUBLISHED,
        "domain": SpecDomain(service="persona", language="go"),
        "inputs": [SpecInput(name="refresh_token", type="string")],
        "outputs": [SpecOutput(name="new_token", type="string", constraints=["exp=15m"])],
        "invariants": ["Refresh tokens are single-use"],
        "acceptance_criteria": [
            AcceptanceCriterion(criterion="Valid refresh produces new token pair", satisfaction_weight=0.6),
            AcceptanceCriterion(criterion="Reused token triggers revocation", satisfaction_weight=0.4),
        ],
    }
    defaults.update(overrides)
    return Spec(**defaults)


class TestValidator:
    def test_valid_spec(self) -> None:
        result = validate_spec(_make_spec())
        assert result.valid
        assert not result.errors

    def test_bad_id_format(self) -> None:
        result = validate_spec(_make_spec(id="bad-id"))
        assert not result.valid
        assert any("format" in e for e in result.errors)

    def test_bad_version(self) -> None:
        result = validate_spec(_make_spec(version="abc"))
        assert not result.valid

    def test_no_criteria(self) -> None:
        result = validate_spec(_make_spec(acceptance_criteria=[]))
        assert not result.valid

    def test_weight_mismatch(self) -> None:
        result = validate_spec(
            _make_spec(
                acceptance_criteria=[
                    AcceptanceCriterion(criterion="A", satisfaction_weight=0.3),
                    AcceptanceCriterion(criterion="B", satisfaction_weight=0.3),
                ]
            )
        )
        assert not result.valid
        assert any("weights" in e.lower() for e in result.errors)

    def test_warns_no_invariants(self) -> None:
        result = validate_spec(_make_spec(invariants=[]))
        assert result.valid
        assert result.warnings


class TestCompiler:
    def test_compile_published_spec(self) -> None:
        spec = _make_spec()
        result = compile_spec(spec)
        assert not result.errors
        assert len(result.scenarios) == 3  # 2 criteria + 1 invariant

    def test_compile_draft_rejected(self) -> None:
        spec = _make_spec(state=SpecState.DRAFT)
        result = compile_spec(spec)
        assert result.errors
        assert len(result.scenarios) == 0

    def test_invariant_scenarios(self) -> None:
        spec = _make_spec()
        result = compile_spec(spec)
        inv_scenarios = [s for s in result.scenarios if "INVARIANT" in s.criterion_ref]
        assert len(inv_scenarios) == 1
        assert "adversary" in inv_scenarios[0].steps[0].actor


@pytest.mark.asyncio
async def test_validate_endpoint(client: AsyncClient) -> None:
    spec = _make_spec()
    resp = await client.post("/specs/validate", json={"spec": spec.model_dump()})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


@pytest.mark.asyncio
async def test_compile_endpoint(client: AsyncClient) -> None:
    spec = _make_spec()
    resp = await client.post("/specs/compile", json={"spec": spec.model_dump()})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scenarios"]) == 3
    assert data["spec_id"] == spec.id
