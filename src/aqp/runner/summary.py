"""Aggregate per-feature outcomes into a suite summary for CI (PRD §8).

Token accounting is carried through as a quality signal, not just a cost line.
"""

from __future__ import annotations

from collections.abc import Sequence

from aqp.models import (
    FeatureOutcome,
    ScenarioResult,
    StepStatus,
    SuiteSummary,
    TokenUsage,
)


def summarize(
    outcomes: Sequence[FeatureOutcome],
    *,
    missing_reports: Sequence[str] = (),
    max_parallel: int = 2,
) -> SuiteSummary:
    tokens = TokenUsage()
    steps_total = 0
    steps_passed = 0
    duration = 0.0
    passed = failed = blocked = 0

    for outcome in outcomes:
        if outcome.result is ScenarioResult.PASSED:
            passed += 1
        elif outcome.result is ScenarioResult.BLOCKED:
            blocked += 1
        else:
            failed += 1
        for scenario in outcome.scenarios:
            tokens = tokens + scenario.tokens
            duration += scenario.duration_s
            steps_total += scenario.steps_total
            steps_passed += sum(1 for s in scenario.steps if s.status is StepStatus.PASSED)

    return SuiteSummary(
        features_total=len(outcomes),
        features_passed=passed,
        features_failed=failed,
        features_blocked=blocked,
        missing_reports=list(missing_reports),
        steps_total=steps_total,
        steps_passed=steps_passed,
        tokens=tokens,
        duration_s=round(duration, 3),
        max_parallel=max_parallel,
    )
