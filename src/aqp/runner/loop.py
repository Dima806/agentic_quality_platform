"""The loop controller (PRD §6) -- fully deterministic.

Per step, in order: act, judge. Bounded retries (at most ``max_attempts``);
first *real* failure ends the scenario; every remaining step is ``SKIPPED``.
An ``infrastructure`` failure blocks the scenario rather than failing it.

Only this file decides retry/stop/skip; the model never does. It is driven
entirely through the :mod:`aqp.ports` Protocols, so it is tested with fakes.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from aqp.assertions.engine import compare_table, expected_table
from aqp.config import Config
from aqp.errors import InfrastructureError
from aqp.models import (
    FailureClass,
    Scenario,
    ScenarioReport,
    ScenarioResult,
    Step,
    StepReport,
    StepStatus,
    StepType,
    TokenUsage,
    ToolCall,
)
from aqp.ports import Browser, StepEvaluator, StepExecutor

OnStep = Callable[[StepReport], None]


@dataclass
class _Attempt:
    status: StepStatus
    failure_class: FailureClass | None = None
    reason: str = ""
    retryable: bool = False
    tokens: TokenUsage = field(default_factory=TokenUsage)
    trace: list[ToolCall] = field(default_factory=list)


def run_scenario(
    scenario: Scenario,
    *,
    feature_name: str,
    browser: Browser,
    executor: StepExecutor,
    evaluator: StepEvaluator,
    config: Config,
    on_step: OnStep | None = None,
    screenshot_dir: Path | None = None,
) -> ScenarioReport:
    started = time.monotonic()
    reports: list[StepReport] = []
    total_tokens = TokenUsage()
    result = ScenarioResult.PASSED
    blocked_reason: str | None = None
    stopped = False

    for step in scenario.steps:
        if stopped:
            report = StepReport(
                n=step.index, text=step.text, keyword=step.keyword, status=StepStatus.SKIPPED
            )
        else:
            report = _run_step(
                step,
                browser=browser,
                executor=executor,
                evaluator=evaluator,
                config=config,
                screenshot_dir=screenshot_dir,
            )
            if report.status is not StepStatus.PASSED:
                stopped = True  # fail fast
                if report.failure_class is FailureClass.INFRASTRUCTURE:
                    result = ScenarioResult.BLOCKED
                    blocked_reason = report.reason
                else:
                    result = ScenarioResult.FAILED

        total_tokens = total_tokens + report.tokens
        reports.append(report)
        if on_step is not None:
            on_step(report)

    return ScenarioReport(
        feature=feature_name,
        scenario=scenario.name,
        result=result,
        steps_total=len(scenario.steps),
        steps_passed=sum(1 for r in reports if r.status is StepStatus.PASSED),
        steps=reports,
        tokens=total_tokens,
        duration_s=round(time.monotonic() - started, 3),
        blocked_reason=blocked_reason,
    )


def _run_step(
    step: Step,
    *,
    browser: Browser,
    executor: StepExecutor,
    evaluator: StepEvaluator,
    config: Config,
    screenshot_dir: Path | None,
) -> StepReport:
    tokens = TokenUsage()
    last = _Attempt(status=StepStatus.FAILED)
    attempts = 0

    while attempts < config.max_attempts:
        attempts += 1
        try:
            last = _attempt(step, browser.snapshot(), executor=executor, evaluator=evaluator)
        except InfrastructureError as exc:
            last = _Attempt(
                status=StepStatus.FAILED,
                failure_class=FailureClass.INFRASTRUCTURE,
                reason=str(exc),
            )
        tokens = tokens + last.tokens

        if last.status is StepStatus.PASSED:
            break
        if not (last.retryable and attempts < config.max_attempts):
            break

    return StepReport(
        n=step.index,
        text=step.text,
        keyword=step.keyword,
        status=last.status,
        attempts=attempts,
        retried=attempts > 1,
        reason=last.reason or None,
        failure_class=last.failure_class,
        screenshot=_capture(browser, screenshot_dir, step),
        trace=last.trace,
        tokens=tokens,
    )


def _attempt(
    step: Step, snapshot: str, *, executor: StepExecutor, evaluator: StepEvaluator
) -> _Attempt:
    if _is_data_assertion(step):
        return _check_data(step, snapshot, executor)
    return _check_action(step, snapshot, executor, evaluator)


def _is_data_assertion(step: Step) -> bool:
    """A ``Then`` carrying a data table is checked in code (PRD §7).

    Other ``Then`` forms (a bare quoted value or doc-string) are judged by the
    model for now; the engine's exact-match path covers tables, including the
    numeric cells that must never be rounded.
    """
    return step.type is StepType.THEN and step.datatable is not None and bool(step.datatable.rows)


def _check_data(step: Step, snapshot: str, executor: StepExecutor) -> _Attempt:
    expected = expected_table(step)
    columns = expected[0] if expected else []
    extracted = executor.extract_table(step, snapshot, columns)
    result = compare_table(expected, extracted.rows)
    if result.ok:
        return _Attempt(status=StepStatus.PASSED, tokens=extracted.tokens)
    return _Attempt(
        status=StepStatus.FAILED,
        failure_class=FailureClass.DEFECT,  # a data mismatch is a real defect, not retried
        reason="assertion mismatch: " + "; ".join(result.mismatches),
        retryable=False,
        tokens=extracted.tokens,
    )


def _check_action(
    step: Step, snapshot: str, executor: StepExecutor, evaluator: StepEvaluator
) -> _Attempt:
    act = executor.act(step, snapshot)
    judgement = evaluator.judge(step, act)
    tokens = act.tokens + judgement.tokens
    verdict = judgement.verdict
    if verdict.passed:
        return _Attempt(status=StepStatus.PASSED, tokens=tokens, trace=act.trace)
    return _Attempt(
        status=StepStatus.FAILED,
        failure_class=verdict.failure_class,
        reason=verdict.reason,
        retryable=verdict.retryable,
        tokens=tokens,
        trace=act.trace,
    )


def _capture(browser: Browser, screenshot_dir: Path | None, step: Step) -> str | None:
    if screenshot_dir is None:
        return None
    dest = screenshot_dir / f"step-{step.index:02d}.png"
    try:
        return str(dest) if browser.screenshot(dest) else None
    except Exception:  # noqa: BLE001 - screenshots are best-effort evidence, never fatal
        return None
