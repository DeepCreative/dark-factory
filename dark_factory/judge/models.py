"""Pydantic models for the Judge-01 Scenario Eval API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvaluateRequest(BaseModel):
    """Request body forwarded by SDSM's POST /api/dark-factory/evaluate."""

    prompt: str = Field(..., description="Pre-built evaluation prompt from SDSM")
    trajectory_log: dict[str, Any] = Field(..., description="Full trajectory log of the scenario execution")
    satisfaction_criterion: str = Field(..., description="Natural-language satisfaction criterion to score against")


class EvaluateResponse(BaseModel):
    """Structured evaluation result returned to SDSM."""

    model_config = ConfigDict(protected_namespaces=())

    score: float = Field(..., ge=0.0, le=1.0, description="Satisfaction score in [0, 1]")
    reasoning: str | None = Field(default=None, description="Optional chain-of-thought reasoning")
    model_version: str | None = Field(default=None, description="Model or backend version that produced this score")
