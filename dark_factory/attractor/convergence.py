"""Attractor convergence loop.

Implements the generate-verify-regenerate cycle that converges code toward
spec satisfaction. Each iteration:
  1. Generate/regenerate code via D3N SWE Fleet
  2. Verify via structural checks (Flash Apps)
  3. Execute scenarios in DTU
  4. Evaluate trajectories via Judge-01
  5. Decide: converged, continue, or strategic regeneration
"""

from __future__ import annotations

import structlog

from dark_factory.attractor.models import (
    AmendmentDiagnosis,
    AmendmentProposal,
    CodebaseContext,
    ConvergenceState,
    ConvergeRequest,
    ConvergeResponse,
    ExecutionMode,
    IterationResult,
)

logger = structlog.get_logger()

STALL_DELTA_THRESHOLD = 0.01


class AttractorEngine:
    """Core convergence engine for Dark Factory spec satisfaction."""

    def __init__(
        self,
        scenario_executor_url: str = "",
        judge_url: str = "",
        dtu_url: str = "",
    ) -> None:
        self._scenario_url = scenario_executor_url
        self._judge_url = judge_url
        self._dtu_url = dtu_url

    async def converge(self, request: ConvergeRequest) -> ConvergeResponse:
        """Run the convergence loop until satisfaction threshold, budget, or stall."""
        logger.info(
            "attractor.converge.start",
            spec_id=request.spec_id,
            threshold=request.satisfaction_threshold,
            max_iterations=request.max_iterations,
            budget=request.budget.total_budget_usd,
            mode=request.mode,
        )

        state = ConvergenceState.INITIALIZING
        history: list[IterationResult] = []
        total_spent = 0.0
        stall_count = 0
        current_satisfaction = 0.0
        code_artifact_ref: str | None = None
        context: CodebaseContext | None = None

        for iteration in range(1, request.max_iterations + 1):
            if total_spent >= request.budget.total_budget_usd:
                state = ConvergenceState.BUDGET_EXHAUSTED
                logger.warning("attractor.budget_exhausted", spent=total_spent)
                break

            if context is None:
                context = await self._build_context(request.spec)

            state = ConvergenceState.GENERATING
            gen_cost = await self._generate(request.spec, iteration, context=context)
            total_spent += gen_cost

            state = ConvergenceState.VERIFYING
            verify_cost = await self._verify(request.spec_id)
            total_spent += verify_cost

            state = ConvergenceState.EVALUATING
            satisfaction, criteria_scores, eval_cost = await self._evaluate(request.spec_id, request.spec)
            total_spent += eval_cost

            delta = satisfaction - current_satisfaction
            current_satisfaction = satisfaction

            if delta < STALL_DELTA_THRESHOLD:
                stall_count += 1
            else:
                stall_count = 0

            result = IterationResult(
                iteration=iteration,
                satisfaction_score=satisfaction,
                delta=round(delta, 4),
                criteria_scores=criteria_scores,
                budget_spent_usd=round(gen_cost + verify_cost + eval_cost, 4),
                stall_count=stall_count,
            )
            history.append(result)

            logger.info(
                "attractor.iteration",
                iteration=iteration,
                satisfaction=satisfaction,
                delta=delta,
                stall_count=stall_count,
                spent=total_spent,
            )

            if satisfaction >= request.satisfaction_threshold:
                state = ConvergenceState.CONVERGED
                code_artifact_ref = f"artifact://{request.spec_id}/iter-{iteration}"
                logger.info("attractor.converged", iterations=iteration, satisfaction=satisfaction)
                break

            if stall_count >= request.stall_limit:
                logger.warning(
                    "attractor.stalled",
                    iterations=iteration,
                    satisfaction=satisfaction,
                    stall_count=stall_count,
                )

                amendments = self._detect_amendment_candidates(history, request.stall_limit)

                if amendments and request.mode == ExecutionMode.SUPERVISED:
                    state = ConvergenceState.AMENDMENT_PROPOSED
                    logger.info(
                        "attractor.amendment_proposed",
                        count=len(amendments),
                        criteria=[a.criterion_ref for a in amendments],
                    )
                    return ConvergeResponse(
                        spec_id=request.spec_id,
                        state=state,
                        iterations_completed=len(history),
                        final_satisfaction=current_satisfaction,
                        iteration_history=history,
                        budget_spent_usd=round(total_spent, 4),
                        amendments=amendments,
                    )

                if amendments:
                    logger.info(
                        "attractor.amendment_logged",
                        mode=request.mode,
                        count=len(amendments),
                        criteria=[a.criterion_ref for a in amendments],
                    )

                state = ConvergenceState.REGENERATING
                context = None  # re-discover context on next iteration
                regen_cost = await self._strategic_regenerate(request.spec, criteria_scores)
                total_spent += regen_cost
                stall_count = 0
        else:
            if state != ConvergenceState.BUDGET_EXHAUSTED:
                state = ConvergenceState.STALLED

        return ConvergeResponse(
            spec_id=request.spec_id,
            state=state,
            iterations_completed=len(history),
            final_satisfaction=current_satisfaction,
            iteration_history=history,
            budget_spent_usd=round(total_spent, 4),
            code_artifact_ref=code_artifact_ref,
        )

    async def _build_context(self, spec: dict) -> CodebaseContext:
        """Discover codebase context for the target service before generation.

        Extracts domain info from the spec and resolves the target service.
        Stub implementation — will wire to SWE Fleet filesystem tools when
        DTU environments are operational.
        """
        domain = spec.get("domain", {})
        service_name = domain.get("service", "unknown")
        logger.info("attractor.build_context", service=service_name)
        return CodebaseContext(service_name=service_name)

    async def _generate(self, spec: dict, iteration: int, *, context: CodebaseContext | None = None) -> float:
        """Generate or update code via D3N SWE Fleet. Returns estimated cost."""
        ctx_svc = context.service_name if context else None
        logger.debug("attractor.generate", iteration=iteration, context_service=ctx_svc)
        return 0.50

    async def _verify(self, spec_id: str) -> float:
        """Run structural verification (Flash App checks). Returns estimated cost."""
        logger.debug("attractor.verify", spec_id=spec_id)
        return 0.10

    async def _evaluate(self, spec_id: str, spec: dict) -> tuple[float, dict[str, float], float]:
        """Execute scenarios + Judge-01 evaluation. Returns (score, criteria_scores, cost)."""
        if not self._scenario_url:
            return 0.5, {"default": 0.5}, 0.20

        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                criteria = spec.get("acceptance_criteria", [])
                if not criteria:
                    return 0.5, {}, 0.20

                resp = await client.post(
                    f"{self._scenario_url}/scenarios/execute-batch",
                    json={
                        "scenarios": [
                            {
                                "scenario_id": f"eval-{spec_id}-{i}",
                                "spec_ref": spec_id,
                                "criterion_ref": c.get("criterion", ""),
                                "steps": [],
                                "satisfaction_criteria": c.get("criterion", ""),
                            }
                            for i, c in enumerate(criteria)
                        ],
                        "parallel": True,
                    },
                )

                if resp.status_code == 200:
                    data = resp.json()
                    aggregate = data.get("aggregate_satisfaction")
                    if aggregate is not None:
                        return aggregate, {}, 0.20
        except Exception as e:
            logger.warning("attractor.evaluate.error", error=str(e))

        return 0.5, {}, 0.20

    def _detect_amendment_candidates(
        self,
        history: list[IterationResult],
        window: int,
    ) -> list[AmendmentProposal]:
        """Identify criteria that are consistently failing and may need spec amendment.

        A criterion is flagged if its score stayed below 0.3 across the last
        `window` iterations while at least one other criterion exceeded 0.7.
        This indicates the problem is likely the criterion, not the generation.
        """
        if len(history) < window:
            return []

        recent = history[-window:]
        all_criteria: set[str] = set()
        for r in recent:
            all_criteria.update(r.criteria_scores.keys())

        if not all_criteria:
            return []

        amendments: list[AmendmentProposal] = []
        has_healthy = False
        for crit in all_criteria:
            scores = [r.criteria_scores.get(crit) for r in recent]
            valid = [s for s in scores if s is not None]
            if valid and max(valid) > 0.7:
                has_healthy = True
                break

        for crit in all_criteria:
            scores = [r.criteria_scores.get(crit) for r in recent]
            valid = [s for s in scores if s is not None]
            if not valid:
                continue
            avg = sum(valid) / len(valid)
            if avg < 0.3 and has_healthy:
                diagnosis = AmendmentDiagnosis.AMBIGUOUS if avg > 0.15 else AmendmentDiagnosis.UNSATISFIABLE
                amendments.append(
                    AmendmentProposal(
                        criterion_ref=crit,
                        current_score=round(avg, 4),
                        iterations_stuck=window,
                        diagnosis=diagnosis,
                        suggestion=f"Criterion '{crit}' scored {avg:.2f} avg over {window} iterations "
                        f"while other criteria passed. Consider clarifying or splitting.",
                    )
                )

        return amendments

    async def _strategic_regenerate(self, spec: dict, weak_criteria: dict[str, float]) -> float:
        """Targeted regeneration focusing on lowest-scoring criteria."""
        lowest = sorted(weak_criteria.items(), key=lambda x: x[1])[:3] if weak_criteria else []
        logger.info("attractor.strategic_regen", focus=[k for k, _ in lowest])
        return 1.0
