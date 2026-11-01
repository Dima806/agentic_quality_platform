"""The evaluator: judges a step and separates defects from recoverable issues.

A transient hiccup is 'execution' (retryable); a wrong page or unmet expectation
is a 'defect' (not retried -- the bug you wanted); a broken environment is
'infrastructure' (the run is blocked, not failed). See the table in PRD §6.
"""

from __future__ import annotations

from aqp.agents.prompts import EVALUATOR_SYSTEM, SUBMIT_VERDICT_TOOL, evaluator_prompt
from aqp.models import FailureClass, Step, Verdict
from aqp.ports import LLM, ActResult, Judgement

_FAILURE_CLASSES = {c.value for c in FailureClass}


class Evaluator:
    """Implements :class:`aqp.ports.StepEvaluator`."""

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    def judge(self, step: Step, act: ActResult) -> Judgement:
        result = self._llm.structured(
            system=EVALUATOR_SYSTEM,
            prompt=evaluator_prompt(step, act.summary, act.final_snapshot),
            tool=SUBMIT_VERDICT_TOOL,
        )
        data = result.data

        if bool(data.get("passed", False)):
            return Judgement(verdict=Verdict(passed=True), tokens=result.tokens)

        raw_class = data.get("failure_class")
        failure_class = (
            FailureClass(raw_class) if raw_class in _FAILURE_CLASSES else FailureClass.EXECUTION
        )
        # Default retryability follows the class unless the model says otherwise.
        retryable = bool(data.get("retryable", failure_class is FailureClass.EXECUTION))
        verdict = Verdict(
            passed=False,
            failure_class=failure_class,
            retryable=retryable,
            reason=str(data.get("reason", "")),
        )
        return Judgement(verdict=verdict, tokens=result.tokens)
