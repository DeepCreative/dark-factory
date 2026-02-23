"""Scenario execution engine.

Runs scenario steps against DTU twin environments and collects trajectory logs.
The executor calls into the DTU Controller for environment provisioning and
forwards completed trajectories to Judge-01 for satisfaction scoring.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import structlog

from dark_factory.scenario_executor.models import (
    ExecuteRequest,
    ExecuteResponse,
    ScenarioStatus,
    StepResult,
    TrajectoryLog,
)

logger = structlog.get_logger()


class ScenarioExecutor:
    """Executes scenario steps against DTU twin endpoints."""

    def __init__(self, dtu_base_url: str = "", judge_url: str = "") -> None:
        self._dtu_base_url = dtu_base_url
        self._judge_url = judge_url

    async def execute(self, request: ExecuteRequest) -> ExecuteResponse:
        """Execute a single scenario and return the trajectory with optional judge score."""
        start = time.monotonic()
        trajectory_id = f"traj-{uuid.uuid4().hex[:12]}"

        logger.info(
            "scenario.execute.start",
            scenario_id=request.scenario_id,
            spec_ref=request.spec_ref,
            steps=len(request.steps),
        )

        step_results: list[StepResult] = []
        passed = 0
        failed = 0

        for i, step in enumerate(request.steps):
            step_id = f"step-{i}"
            step_result = await self._execute_step(step_id, step, request.dtu_namespace)
            step_results.append(step_result)
            if step_result.assertions_passed:
                passed += 1
            else:
                failed += 1

        trajectory = TrajectoryLog(
            trajectory_id=trajectory_id,
            scenario_id=request.scenario_id,
            steps=step_results,
            structural_assertions={"passed": passed, "failed": failed, "total": len(step_results)},
        )

        satisfaction_score: float | None = None
        judge_reasoning: str | None = None

        if self._judge_url:
            satisfaction_score, judge_reasoning = await self._call_judge(trajectory, request.satisfaction_criteria)

        elapsed = round((time.monotonic() - start) * 1000, 2)
        status = ScenarioStatus.COMPLETED if failed == 0 else ScenarioStatus.FAILED

        logger.info(
            "scenario.execute.done",
            scenario_id=request.scenario_id,
            status=status,
            passed=passed,
            failed=failed,
            satisfaction=satisfaction_score,
            elapsed_ms=elapsed,
        )

        return ExecuteResponse(
            scenario_id=request.scenario_id,
            status=status,
            trajectory=trajectory,
            satisfaction_score=satisfaction_score,
            judge_reasoning=judge_reasoning,
            elapsed_ms=elapsed,
        )

    async def _execute_step(
        self,
        step_id: str,
        step: dict[str, str],
        dtu_namespace: str | None,
    ) -> StepResult:
        """Execute a single scenario step against the DTU environment."""
        action = step.get("action", "")
        expected = step.get("expect", "")

        if not self._dtu_base_url:
            return StepResult(
                step_id=step_id,
                request={"action": action, "dtu_namespace": dtu_namespace},
                response={"status": 200, "body": {"mode": "stub", "expected": expected}},
                assertions_passed=True,
                latency_ms=1.0,
            )

        import httpx

        try:
            async with httpx.AsyncClient(base_url=self._dtu_base_url, timeout=30.0) as client:
                start = time.monotonic()
                resp = await client.post(
                    "/execute-step",
                    json={"step_id": step_id, "action": action, "namespace": dtu_namespace},
                )
                latency = round((time.monotonic() - start) * 1000, 2)

                body = resp.json()
                return StepResult(
                    step_id=step_id,
                    request={"action": action, "dtu_namespace": dtu_namespace},
                    response={"status": resp.status_code, "body": body},
                    assertions_passed=body.get("assertions_passed", resp.status_code == 200),
                    latency_ms=latency,
                )
        except Exception as e:
            logger.warning("scenario.step.error", step_id=step_id, error=str(e))
            return StepResult(
                step_id=step_id,
                request={"action": action},
                response={},
                assertions_passed=False,
                error=str(e),
            )

    async def _call_judge(self, trajectory: TrajectoryLog, criterion: str) -> tuple[float | None, str | None]:
        """Forward trajectory to Judge-01 for satisfaction scoring."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._judge_url}/evaluate",
                    json={
                        "prompt": f"Evaluate trajectory against: {criterion}",
                        "trajectory_log": trajectory.model_dump(),
                        "satisfaction_criterion": criterion,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("score"), data.get("reasoning")
        except Exception as e:
            logger.warning("scenario.judge.error", error=str(e))

        return None, None

    async def execute_batch(
        self,
        requests: list[ExecuteRequest],
        max_concurrency: int = 5,
    ) -> list[ExecuteResponse]:
        """Execute multiple scenarios with bounded concurrency."""
        sem = asyncio.Semaphore(max_concurrency)

        async def _run(req: ExecuteRequest) -> ExecuteResponse:
            async with sem:
                return await self.execute(req)

        return await asyncio.gather(*[_run(r) for r in requests])
