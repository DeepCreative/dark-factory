"""Tests for the Attractor convergence agent."""

from __future__ import annotations

import pytest
from dark_factory.attractor.convergence import AttractorEngine
from dark_factory.attractor.models import (
    AmendmentDiagnosis,
    BudgetAllocation,
    ConvergenceState,
    ConvergeRequest,
    ExecutionMode,
    IterationResult,
)
from dark_factory.attractor.task_entropy import (
    AttractorEntropyConfig,
    AttractorEntropyEstimator,
)
from httpx import AsyncClient


def _make_request(**overrides) -> ConvergeRequest:
    defaults = {
        "spec_id": "spec-20260219-auth",
        "spec_version": "1.0.0",
        "spec": {
            "acceptance_criteria": [
                {"criterion": "Valid refresh", "satisfaction_weight": 0.5},
                {"criterion": "Token revocation", "satisfaction_weight": 0.5},
            ]
        },
        "satisfaction_threshold": 0.90,
        "max_iterations": 5,
        "budget": BudgetAllocation(total_budget_usd=10.0),
        "mode": ExecutionMode.AUTONOMOUS,
    }
    defaults.update(overrides)
    return ConvergeRequest(**defaults)


@pytest.mark.asyncio
async def test_convergence_runs() -> None:
    engine = AttractorEngine()
    result = await engine.converge(_make_request())
    assert result.spec_id == "spec-20260219-auth"
    assert result.iterations_completed > 0
    assert result.budget_spent_usd > 0


@pytest.mark.asyncio
async def test_budget_exhaustion() -> None:
    engine = AttractorEngine()
    result = await engine.converge(
        _make_request(
            budget=BudgetAllocation(total_budget_usd=0.5),
            max_iterations=20,
        )
    )
    assert result.state == ConvergenceState.BUDGET_EXHAUSTED


@pytest.mark.asyncio
async def test_iteration_history() -> None:
    engine = AttractorEngine()
    result = await engine.converge(_make_request(max_iterations=3))
    assert len(result.iteration_history) <= 3
    for h in result.iteration_history:
        assert h.iteration > 0
        assert 0.0 <= h.satisfaction_score <= 1.0


@pytest.mark.asyncio
async def test_converge_endpoint(client: AsyncClient) -> None:
    resp = await client.post("/attractor/converge", json=_make_request().model_dump())
    assert resp.status_code == 200
    data = resp.json()
    assert data["spec_id"] == "spec-20260219-auth"
    assert data["iterations_completed"] > 0


@pytest.mark.asyncio
async def test_status_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/attractor/status/spec-nonexistent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "initializing"


# ---------- amendment detection ----------


def test_detect_amendment_candidates_flags_low_criterion() -> None:
    """Criteria consistently < 0.3 while others > 0.7 produce amendments."""
    engine = AttractorEngine()
    history = [
        IterationResult(
            iteration=i,
            satisfaction_score=0.5,
            criteria_scores={"good_crit": 0.85, "bad_crit": 0.1},
        )
        for i in range(1, 4)
    ]
    amendments = engine._detect_amendment_candidates(history, window=3)
    assert len(amendments) == 1
    assert amendments[0].criterion_ref == "bad_crit"
    assert amendments[0].diagnosis in (AmendmentDiagnosis.AMBIGUOUS, AmendmentDiagnosis.UNSATISFIABLE)


def test_detect_amendment_no_flag_when_criteria_uniform() -> None:
    """No amendments when all criteria are uniformly low (problem is generation, not spec)."""
    engine = AttractorEngine()
    history = [
        IterationResult(
            iteration=i,
            satisfaction_score=0.2,
            criteria_scores={"crit_a": 0.2, "crit_b": 0.25},
        )
        for i in range(1, 4)
    ]
    amendments = engine._detect_amendment_candidates(history, window=3)
    assert amendments == []


def test_detect_amendment_no_flag_when_history_too_short() -> None:
    """No amendments when history is shorter than the window."""
    engine = AttractorEngine()
    history = [
        IterationResult(iteration=1, satisfaction_score=0.5, criteria_scores={"a": 0.1, "b": 0.9}),
    ]
    amendments = engine._detect_amendment_candidates(history, window=3)
    assert amendments == []


@pytest.mark.asyncio
async def test_amendment_proposed_in_supervised_mode() -> None:
    """Supervised mode returns AMENDMENT_PROPOSED when criteria diverge."""

    class StubbedEngine(AttractorEngine):
        async def _generate(self, spec, iteration, *, context=None):
            return 0.10

        async def _verify(self, spec_id):
            return 0.05

        async def _evaluate(self, spec_id, spec):
            return 0.45, {"good": 0.85, "bad": 0.05}, 0.05

    engine = StubbedEngine()
    result = await engine.converge(
        _make_request(
            mode=ExecutionMode.SUPERVISED,
            stall_limit=2,
            max_iterations=10,
            satisfaction_threshold=0.95,
        )
    )
    assert result.state == ConvergenceState.AMENDMENT_PROPOSED
    assert len(result.amendments) == 1
    assert result.amendments[0].criterion_ref == "bad"


@pytest.mark.asyncio
async def test_amendment_logged_in_autonomous_mode() -> None:
    """Autonomous mode logs amendments but continues with strategic regeneration."""

    class StubbedEngine(AttractorEngine):
        async def _generate(self, spec, iteration, *, context=None):
            return 0.10

        async def _verify(self, spec_id):
            return 0.05

        async def _evaluate(self, spec_id, spec):
            return 0.45, {"good": 0.85, "bad": 0.05}, 0.05

    engine = StubbedEngine()
    result = await engine.converge(
        _make_request(
            mode=ExecutionMode.AUTONOMOUS,
            stall_limit=2,
            max_iterations=10,
            budget=BudgetAllocation(total_budget_usd=5.0),
        )
    )
    # Should NOT be AMENDMENT_PROPOSED — autonomous mode continues
    assert result.state != ConvergenceState.AMENDMENT_PROPOSED


# ---------- task entropy estimator ----------


class TestAttractorEntropyEstimator:
    """Tests for the AttractorEntropyEstimator."""

    def test_minimal_spec_low_entropy(self) -> None:
        """A minimal spec with few signals produces low entropy."""
        estimator = AttractorEntropyEstimator()
        spec = {"description": "Fix a typo", "acceptance_criteria": []}
        result = estimator.estimate(spec)
        assert 0.0 <= result.score <= 1.0
        assert result.score < 0.35
        assert result.routing == "flat"

    def test_complex_spec_high_entropy(self) -> None:
        """A complex spec with many files and dependencies produces high entropy."""
        estimator = AttractorEntropyEstimator()
        spec = {
            "description": (
                "Refactor the authentication module to support OAuth 2.1 with PKCE, "
                "migrate the session store from Redis to PostgreSQL, add integration "
                "tests for all token flows, update API docs, and design a rollback "
                "strategy for the database migration across environments"
            ),
            "target_files": [f"src/auth/file_{i}.py" for i in range(15)],
            "dependencies": ["redis", "postgresql", "httpx", "jose", "pydantic", "alembic"],
            "requires_new_files": True,
            "domain": {"complexity": "high"},
        }
        result = estimator.estimate(spec)
        assert result.score >= 0.65
        assert result.routing == "structured"

    def test_medium_complexity_routes_flat_decomposed(self) -> None:
        """A moderately complex spec routes to flat_decomposed."""
        estimator = AttractorEntropyEstimator()
        spec = {
            "description": (
                "Add a new API endpoint for user profile updates with input validation, "
                "error handling, database migrations for the new fields, and unit tests "
                "covering edge cases for partial updates and concurrent modifications"
            ),
            "target_files": [
                "src/api/users.py",
                "src/models/user.py",
                "src/validators/profile.py",
                "tests/test_users.py",
                "migrations/add_profile_fields.py",
                "src/api/schemas.py",
            ],
            "dependencies": ["pydantic", "httpx", "sqlalchemy", "alembic"],
            "domain": {"complexity": "medium"},
        }
        result = estimator.estimate(spec)
        assert 0.35 <= result.score <= 0.65
        assert result.routing == "flat_decomposed"

    def test_custom_config_shifts_thresholds(self) -> None:
        """Custom config theta_low/theta_high changes routing classification."""
        config = AttractorEntropyConfig(theta_low=0.0, theta_high=0.1)
        estimator = AttractorEntropyEstimator(config=config)
        spec = {
            "description": "Add input validation to the form handler with error messages",
            "target_files": ["src/forms.py", "src/validators.py"],
            "dependencies": ["pydantic"],
            "domain": {"complexity": "medium"},
        }
        result = estimator.estimate(spec)
        assert result.score > 0.1
        assert result.routing == "structured"

    def test_signals_included_in_result(self) -> None:
        """Entropy estimate includes raw signal values."""
        estimator = AttractorEntropyEstimator()
        spec = {
            "description": "Update configuration",
            "target_files": ["config.yaml"],
            "dependencies": [],
        }
        result = estimator.estimate(spec)
        assert "description_length" in result.signals
        assert "file_count" in result.signals
        assert "dependency_count" in result.signals
        assert "requires_new_files" in result.signals
        assert "domain_complexity" in result.signals

    def test_description_fallback_to_criteria(self) -> None:
        """When no description is present, acceptance_criteria text is used."""
        estimator = AttractorEntropyEstimator()
        spec = {
            "acceptance_criteria": [
                {"criterion": "All tokens must be rotated within 24 hours"},
                {"criterion": "Revoked tokens must be rejected immediately"},
            ]
        }
        result = estimator.estimate(spec)
        assert result.signals["description_length"] > 0

    def test_domain_complexity_string_mapping(self) -> None:
        """String-based domain complexity increases entropy score monotonically."""
        estimator = AttractorEntropyEstimator()
        scores: dict[str, float] = {}
        for label in ("low", "medium", "high", "critical"):
            spec = {
                "description": "Task description for complexity testing with enough length to matter",
                "domain": {"complexity": label},
                "target_files": [f"f{i}" for i in range(5)],
                "dependencies": ["dep1", "dep2", "dep3"],
            }
            result = estimator.estimate(spec)
            scores[label] = result.score

        assert scores["low"] < scores["medium"]
        assert scores["medium"] < scores["high"]
        assert scores["high"] < scores["critical"]


# ---------- convergence report includes entropy ----------


@pytest.mark.asyncio
async def test_convergence_report_includes_entropy() -> None:
    """Convergence iteration results include task_entropy and routing."""
    engine = AttractorEngine()
    result = await engine.converge(_make_request(max_iterations=2))
    assert result.iterations_completed > 0
    for h in result.iteration_history:
        assert h.task_entropy is not None
        assert 0.0 <= h.task_entropy <= 1.0
        assert h.task_entropy_routing in ("flat", "flat_decomposed", "structured")


@pytest.mark.asyncio
async def test_entropy_logging(capfd) -> None:
    """Entropy estimation emits structlog events during convergence."""
    import io

    import structlog

    output = io.StringIO()
    structlog.configure(
        processors=[
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        logger_factory=structlog.PrintLoggerFactory(file=output),
    )

    engine = AttractorEngine()
    await engine.converge(_make_request(max_iterations=1))

    log_output = output.getvalue()
    assert "entropy.attractor_routing" in log_output or "attractor.iteration" in log_output
