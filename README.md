# Dark Factory

Dark Factory pipeline services for the Bravo Zero platform: **Spec Engine**, **Attractor**, **Scenario Executor**, and **DTU Controller** per [ADR-151: Dark Factory Architecture](../../docs/cognitive-architecture-docs/docs/adrs/ADR-151-dark-factory-architecture.md).

- **One repo**, one Kubernetes namespace `dark-factory`.
- **Documentation**: [Dark Factory Documentation Index](../../docs/cognitive-architecture-docs/docs/platform/guides/dark-factory-docs-index.md) — architecture, operations, and implementation status.
- **Implementation**: Agent implementations (Spec Engine, Attractor, Scenario Executor, DTU Controller) are phased; this repo is the scaffold. See ADR-151 and the PRDs/specs linked from the docs index.

## Planned components

| Component | Spec / PRD |
|-----------|------------|
| Spec Engine | [Spec Engine PRD](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/spec-engine-prd.md) |
| Attractor | [Attractor Convergence Agent](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/attractor-convergence-agent.md) |
| Scenario Executor | [Scenario Testing Framework](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/scenario-testing-framework.md) |
| DTU Controller | [Digital Twin Universe](../../docs/cognitive-architecture-docs/docs/systems/swe-agent/specs/digital-twin-universe.md) |

Placeholder directories: `spec_engine/`, `attractor/`, `scenario_executor/`, `dtu_controller/` (see each directory's README).

**Setup**: If the GitHub repo does not exist yet, create `DeepCreative/dark-factory`, add the remote (`git remote add origin git@github.com:DeepCreative/dark-factory.git` or the HTTPS URL), then push: `git push -u origin main`.
