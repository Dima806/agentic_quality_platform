"""Suite summary aggregation (PRD §8)."""

from __future__ import annotations

from aqp.models import (
    FeatureOutcome,
    ScenarioReport,
    ScenarioResult,
    StepReport,
    StepStatus,
    TokenUsage,
)
from aqp.runner import summarize


def _report(result: ScenarioResult, passed: int, total: int, tokens: TokenUsage) -> ScenarioReport:
    steps = [
        StepReport(
            n=i,
            text=f"s{i}",
            keyword="Then",
            status=StepStatus.PASSED if i <= passed else StepStatus.FAILED,
        )
        for i in range(1, total + 1)
    ]
    return ScenarioReport(
        feature="F",
        scenario="S",
        result=result,
        steps_total=total,
        steps_passed=passed,
        steps=steps,
        tokens=tokens,
        duration_s=1.5,
    )


def test_summarize_counts_and_tokens() -> None:
    outcomes = [
        FeatureOutcome(
            feature="ok",
            path="ok.feature",
            result=ScenarioResult.PASSED,
            scenarios=[_report(ScenarioResult.PASSED, 3, 3, TokenUsage(prompt=100, completion=10))],
        ),
        FeatureOutcome(
            feature="bad",
            path="bad.feature",
            result=ScenarioResult.FAILED,
            scenarios=[_report(ScenarioResult.FAILED, 1, 4, TokenUsage(prompt=50, completion=5))],
        ),
        FeatureOutcome(
            feature="env",
            path="env.feature",
            result=ScenarioResult.BLOCKED,
            scenarios=[_report(ScenarioResult.BLOCKED, 0, 2, TokenUsage(prompt=20, completion=1))],
        ),
    ]
    summary = summarize(outcomes, missing_reports=["gone.feature"], max_parallel=2)

    assert (summary.features_total, summary.features_passed) == (3, 1)
    assert summary.features_failed == 1
    assert summary.features_blocked == 1
    assert summary.steps_total == 9
    assert summary.steps_passed == 4
    assert summary.tokens.total == 100 + 10 + 50 + 5 + 20 + 1
    assert summary.missing_reports == ["gone.feature"]
    assert summary.max_parallel == 2
