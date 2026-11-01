"""The loop controller: retry cap, fail-fast, skip, and failure classification (PRD §6)."""

from __future__ import annotations

from aqp.config import Config
from aqp.models import FailureClass, Scenario, ScenarioResult, StepStatus, Verdict
from aqp.runner import run_scenario
from conftest import (
    ACT_TOKENS,
    JUDGE_TOKENS,
    FakeBrowser,
    FakeEvaluator,
    FakeExecutor,
    RaisingBrowser,
    make_scenario,
    table_then_step,
)

CONFIG = Config()  # max_attempts = 2


def _run(scenario: Scenario, evaluator: FakeEvaluator, executor: FakeExecutor | None = None):
    return run_scenario(
        scenario,
        feature_name="F",
        browser=FakeBrowser(),
        executor=executor or FakeExecutor(),
        evaluator=evaluator,
        config=CONFIG,
    )


def test_all_steps_pass() -> None:
    scenario = make_scenario(["step one", "step two", "step three"])
    report = _run(scenario, FakeEvaluator())

    assert report.result is ScenarioResult.PASSED
    assert report.steps_passed == 3
    assert all(s.status is StepStatus.PASSED and s.attempts == 1 for s in report.steps)
    assert all(not s.retried for s in report.steps)


def test_retryable_failure_then_pass_is_retried() -> None:
    scenario = make_scenario(["flaky step"])
    evaluator = FakeEvaluator(
        [Verdict(passed=False, failure_class=FailureClass.EXECUTION, retryable=True)]
    )
    report = _run(scenario, evaluator)

    step = report.steps[0]
    assert step.status is StepStatus.PASSED
    assert step.attempts == 2
    assert step.retried
    assert report.result is ScenarioResult.PASSED


def test_retry_cap_stops_after_two_attempts() -> None:
    scenario = make_scenario(["flaky step", "never reached"])
    evaluator = FakeEvaluator(
        [
            Verdict(passed=False, failure_class=FailureClass.EXECUTION, retryable=True),
            Verdict(passed=False, failure_class=FailureClass.EXECUTION, retryable=True),
        ]
    )
    report = _run(scenario, evaluator)

    first, second = report.steps
    assert first.status is StepStatus.FAILED
    assert first.attempts == 2  # the cap, not a third try
    assert second.status is StepStatus.SKIPPED  # fail-fast
    assert report.result is ScenarioResult.FAILED


def test_non_retryable_defect_stops_immediately() -> None:
    scenario = make_scenario(["real defect", "never reached"])
    evaluator = FakeEvaluator(
        [
            Verdict(
                passed=False,
                failure_class=FailureClass.DEFECT,
                retryable=False,
                reason="wrong page",
            )
        ]
    )
    report = _run(scenario, evaluator)

    assert report.steps[0].status is StepStatus.FAILED
    assert report.steps[0].attempts == 1  # not retried — it's the bug we wanted
    assert report.steps[0].failure_class is FailureClass.DEFECT
    assert report.steps[1].status is StepStatus.SKIPPED
    assert report.result is ScenarioResult.FAILED


def test_infrastructure_failure_blocks_scenario() -> None:
    scenario = make_scenario(["needs a browser", "never reached"])
    evaluator = FakeEvaluator(
        [Verdict(passed=False, failure_class=FailureClass.INFRASTRUCTURE, retryable=False)]
    )
    report = _run(scenario, evaluator)

    assert report.result is ScenarioResult.BLOCKED
    assert report.steps[0].failure_class is FailureClass.INFRASTRUCTURE
    assert report.steps[1].status is StepStatus.SKIPPED


def test_browser_that_cannot_start_blocks_scenario() -> None:
    scenario = make_scenario(["open the app"])
    report = run_scenario(
        scenario,
        feature_name="F",
        browser=RaisingBrowser(),
        executor=FakeExecutor(),
        evaluator=FakeEvaluator(),
        config=CONFIG,
    )
    assert report.result is ScenarioResult.BLOCKED
    assert report.steps[0].failure_class is FailureClass.INFRASTRUCTURE


def test_data_table_match_passes_in_code() -> None:
    rows = [["Status", "Amount"], ["Successful", "272.00"]]
    scenario = Scenario(name="refund", steps=[table_then_step(rows)])
    executor = FakeExecutor(table_rows=rows)
    report = _run(scenario, FakeEvaluator(), executor)

    assert report.result is ScenarioResult.PASSED
    assert executor.extract_calls == 1  # the model located values...
    assert executor.act_calls == 0  # ...but the step was judged in code, not driven


def test_data_table_mismatch_is_a_defect_not_retried() -> None:
    expected = [["Status", "Amount"], ["Successful", "272.00"]]
    onscreen = [["Status", "Amount"], ["Successful", "272"]]  # rounded by the app == bug
    scenario = Scenario(name="refund", steps=[table_then_step(expected)])
    executor = FakeExecutor(table_rows=onscreen)
    report = _run(scenario, FakeEvaluator(), executor)

    assert report.result is ScenarioResult.FAILED
    assert report.steps[0].failure_class is FailureClass.DEFECT
    assert report.steps[0].attempts == 1  # a defect is not retried
    assert executor.extract_calls == 1


def test_tokens_are_accumulated_from_each_step() -> None:
    scenario = make_scenario(["one", "two"])
    report = _run(scenario, FakeEvaluator())
    per_step = ACT_TOKENS + JUDGE_TOKENS
    assert report.tokens.total == 2 * per_step.total
    assert report.steps[0].tokens.total == per_step.total


def test_on_step_streams_every_step() -> None:
    scenario = make_scenario(["a", "b", "c"])
    seen = []
    run_scenario(
        scenario,
        feature_name="F",
        browser=FakeBrowser(),
        executor=FakeExecutor(),
        evaluator=FakeEvaluator(),
        config=CONFIG,
        on_step=seen.append,
    )
    assert len(seen) == 3
