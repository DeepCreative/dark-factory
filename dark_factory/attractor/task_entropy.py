"""Sub-task entropy estimator for the Dark Factory Attractor.

Adapts ARIA's TaskEntropyEstimator signal framework to spec-derived tasks.
Produces an entropy score in [0, 1] that indicates how structurally complex
a generation sub-task is, enabling entropy-aware routing when the Attractor
dispatches to the SWE Fleet (or future ARIA Conductor integration).

Signals:
  - description_length: raw character count of task description
  - file_count: number of files in scope for this task
  - dependency_count: number of cross-file or cross-service dependencies
  - requires_new_files: whether task requires creating files vs editing
  - domain_complexity: metadata hint from spec (0-1 scale)

The output feeds into convergence reports and the ARIA calibration pipeline
as labeled training data (entropy + satisfaction outcome).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AttractorEntropyConfig:
    """Configurable thresholds and weights for Attractor entropy estimation."""

    theta_low: float = float(os.environ.get("DF_ENTROPY_THETA_LOW", "0.35"))
    theta_high: float = float(os.environ.get("DF_ENTROPY_THETA_HIGH", "0.65"))

    w_length: float = 0.15
    w_files: float = 0.25
    w_dependencies: float = 0.20
    w_new_files: float = 0.15
    w_domain: float = 0.25


@dataclass
class EntropySignals:
    """Raw signal values extracted from a spec-derived task."""

    description_length: int = 0
    file_count: int = 0
    dependency_count: int = 0
    requires_new_files: bool = False
    domain_complexity: float = 0.0


@dataclass
class EntropyEstimate:
    """Result of entropy estimation for a sub-task."""

    score: float
    routing: str  # "flat", "flat_decomposed", or "structured"
    signals: dict[str, float] = field(default_factory=dict)


class AttractorEntropyEstimator:
    """Estimates task entropy for Attractor sub-tasks."""

    LENGTH_THRESHOLDS = (200, 500, 1000, 2000)
    FILE_THRESHOLDS = (2, 5, 10, 20)
    DEP_THRESHOLDS = (1, 3, 5, 10)

    def __init__(self, config: AttractorEntropyConfig | None = None) -> None:
        self.config = config or AttractorEntropyConfig()

    def estimate(
        self,
        spec: dict,
        iteration: int = 1,
        context_file_count: int = 0,
    ) -> EntropyEstimate:
        """Estimate entropy for a generation task derived from a spec."""
        signals = self._extract_signals(spec, context_file_count)
        score = self._compute_score(signals)
        routing = self._classify(score)

        return EntropyEstimate(
            score=round(score, 4),
            routing=routing,
            signals={
                "description_length": signals.description_length,
                "file_count": signals.file_count,
                "dependency_count": signals.dependency_count,
                "requires_new_files": float(signals.requires_new_files),
                "domain_complexity": signals.domain_complexity,
            },
        )

    def _extract_signals(self, spec: dict, context_file_count: int) -> EntropySignals:
        description = spec.get("description", "")
        if not description:
            criteria = spec.get("acceptance_criteria", [])
            description = " ".join(c.get("criterion", "") for c in criteria if isinstance(c, dict))

        domain = spec.get("domain", {})

        file_count = context_file_count
        if not file_count:
            target_files = spec.get("target_files", [])
            file_count = len(target_files) if target_files else 0

        dependencies = spec.get("dependencies", [])
        dep_count = len(dependencies) if isinstance(dependencies, list) else 0

        requires_new = spec.get("requires_new_files", False)
        if not requires_new:
            changes = spec.get("changes", [])
            requires_new = any(c.get("type") == "create" for c in changes if isinstance(c, dict))

        domain_complexity = domain.get("complexity", 0.0)
        if isinstance(domain_complexity, str):
            complexity_map = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}
            domain_complexity = complexity_map.get(domain_complexity.lower(), 0.5)

        return EntropySignals(
            description_length=len(description),
            file_count=file_count,
            dependency_count=dep_count,
            requires_new_files=requires_new,
            domain_complexity=float(domain_complexity),
        )

    def _compute_score(self, signals: EntropySignals) -> float:
        cfg = self.config

        length_norm = self._threshold_normalize(signals.description_length, self.LENGTH_THRESHOLDS)
        file_norm = self._threshold_normalize(signals.file_count, self.FILE_THRESHOLDS)
        dep_norm = self._threshold_normalize(signals.dependency_count, self.DEP_THRESHOLDS)
        new_files_val = 1.0 if signals.requires_new_files else 0.0
        domain_val = max(0.0, min(1.0, signals.domain_complexity))

        score = (
            cfg.w_length * length_norm
            + cfg.w_files * file_norm
            + cfg.w_dependencies * dep_norm
            + cfg.w_new_files * new_files_val
            + cfg.w_domain * domain_val
        )

        return max(0.0, min(1.0, score))

    def _classify(self, score: float) -> str:
        if score <= self.config.theta_low:
            return "flat"
        elif score >= self.config.theta_high:
            return "structured"
        return "flat_decomposed"

    @staticmethod
    def _threshold_normalize(value: int | float, thresholds: tuple) -> float:
        """Map a value to [0, 1] using threshold breakpoints."""
        if value <= thresholds[0]:
            return 0.0
        for i, t in enumerate(thresholds):
            if value <= t:
                prev = thresholds[i - 1] if i > 0 else 0
                return (i / len(thresholds)) + ((value - prev) / (t - prev)) * (1.0 / len(thresholds))
        return 1.0
