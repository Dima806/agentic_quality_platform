"""Typed records that flow through the pipeline.

Deterministic code is the system of record; these models hold the data, the
assertions, and the evidence. The model never carries asserted values — it only
locates them (PRD §7).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StepType(StrEnum):
    """Semantic keyword of a step (``And``/``But`` normalise to the preceding one)."""

    GIVEN = "given"
    WHEN = "when"
    THEN = "then"


class StepStatus(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ScenarioResult(StrEnum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class FailureClass(StrEnum):
    """Why a step failed — the trust axis (PRD §6)."""

    DEFECT = "defect"  # the app is genuinely wrong; not retried
    EXECUTION = "execution"  # transient; retried up to the attempt limit
    INFRASTRUCTURE = "infrastructure"  # environment broken; run is blocked


# --------------------------------------------------------------------------- #
# Parsed feature structure
# --------------------------------------------------------------------------- #


class DataTable(BaseModel):
    """A Gherkin data table: the first row is the header, the rest are body rows."""

    rows: list[list[str]] = Field(default_factory=list)

    @property
    def header(self) -> list[str]:
        return self.rows[0] if self.rows else []

    @property
    def body(self) -> list[list[str]]:
        return self.rows[1:] if len(self.rows) > 1 else []


class Step(BaseModel):
    """One parsed step. ``text`` is the intent; there is no step definition behind it."""

    index: int  # 1-based position within the scenario
    keyword: str  # surface keyword: Given/When/Then/And/But
    type: StepType  # semantic type
    text: str
    line_number: int
    datatable: DataTable | None = None
    docstring: str | None = None


class Scenario(BaseModel):
    name: str
    steps: list[Step] = Field(default_factory=list)


class Feature(BaseModel):
    name: str
    path: str
    scenarios: list[Scenario] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Judgement
# --------------------------------------------------------------------------- #


class Verdict(BaseModel):
    """The evaluator's decision on a step."""

    passed: bool
    failure_class: FailureClass | None = None
    retryable: bool = False
    reason: str = ""


class AssertionResult(BaseModel):
    """Result of comparing expected vs actual data — computed in code, never by the model."""

    ok: bool
    mismatches: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Tokens & evidence
# --------------------------------------------------------------------------- #


class TokenUsage(BaseModel):
    """Token accounting. A quality signal, not just a cost line (PRD §8)."""

    prompt: int = 0
    completion: int = 0
    cached: int = 0  # cache-read prompt tokens (subset of ``prompt``)
    reasoning: int = 0

    @property
    def total(self) -> int:
        return self.prompt + self.completion

    @property
    def cached_pct(self) -> int:
        return round(100 * self.cached / self.prompt) if self.prompt else 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt=self.prompt + other.prompt,
            completion=self.completion + other.completion,
            cached=self.cached + other.cached,
            reasoning=self.reasoning + other.reasoning,
        )


class ToolCall(BaseModel):
    """One browser tool call, recorded for the trace."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    is_error: bool = False


class StepReport(BaseModel):
    n: int
    text: str
    keyword: str
    status: StepStatus
    attempts: int = 0
    retried: bool = False
    reason: str | None = None
    failure_class: FailureClass | None = None
    screenshot: str | None = None
    trace: list[ToolCall] = Field(default_factory=list)
    tokens: TokenUsage = Field(default_factory=TokenUsage)


class ScenarioReport(BaseModel):
    feature: str
    scenario: str
    result: ScenarioResult
    steps_total: int
    steps_passed: int
    steps: list[StepReport] = Field(default_factory=list)
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    duration_s: float = 0.0
    blocked_reason: str | None = None


class FeatureOutcome(BaseModel):
    """Per-feature roll-up used by the suite summary."""

    feature: str
    path: str
    result: ScenarioResult
    scenarios: list[ScenarioReport] = Field(default_factory=list)


class SuiteSummary(BaseModel):
    features_total: int
    features_passed: int
    features_failed: int
    features_blocked: int
    missing_reports: list[str] = Field(default_factory=list)
    steps_total: int = 0
    steps_passed: int = 0
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    duration_s: float = 0.0
    max_parallel: int = 2
