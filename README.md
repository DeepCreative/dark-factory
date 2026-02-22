# Dark Factory

Dark Factory pipeline services for the Bravo Zero platform: **Judge-01 Scenario Eval** (implemented), **Spec Engine**, **Attractor**, **Scenario Executor**, and **DTU Controller** (phased) per [ADR-151: Dark Factory Architecture](../../docs/cognitive-architecture-docs/docs/adrs/ADR-151-dark-factory-architecture.md).

- **One repo**, one Kubernetes namespace `dark-factory`.
- **Documentation**: [Dark Factory Documentation Index](../../docs/cognitive-architecture-docs/docs/platform/guides/dark-factory-docs-index.md) — architecture, operations, and implementation status.
- **Judge-01 backend**: `POST /evaluate` — scores scenario trajectories against satisfaction criteria using trained D3N models (SageMaker) or a stub for testing. SDSM forwards `POST /api/dark-factory/evaluate` here when `JUDGE_01_SCENARIO_EVAL_URL` is set.

## Components

| Component | Status | Spec / PRD |
|-----------|--------|------------|
| Judge-01 Scenario Eval | Implemented | [Scenario Testing Framework](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/scenario-testing-framework.md) |
| Spec Engine | Planned | [Spec Engine PRD](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/spec-engine-prd.md) |
| Attractor | Planned | [Attractor Convergence Agent](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/attractor-convergence-agent.md) |
| Scenario Executor | Planned | [Scenario Testing Framework](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/scenario-testing-framework.md) |
| DTU Controller | Planned | [Digital Twin Universe](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/digital-twin-universe.md) |

Placeholder directories: `spec_engine/`, `attractor/`, `scenario_executor/`, `dtu_controller/` (see each directory's README).

## Quick start

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
make test

# Start local dev server (stub mode)
JUDGE_BACKEND_MODE=stub uvicorn dark_factory.service.api:app --reload --port 8090

# Or via Docker Compose
make dev
```

## Backend modes

Only D3N models are used in production. LLMs are never backends.

| Mode | Env vars | Use case |
|------|----------|----------|
| `stub` | (none) | Dev/testing — returns fixed 0.5 score |
| `sagemaker` | `SAGEMAKER_ENDPOINT_NAME`, `AWS_DEFAULT_REGION` | Production — trained D3N Judge-01 model |

Set `JUDGE_BACKEND_MODE` to select. See `.env.example` for all configuration.
