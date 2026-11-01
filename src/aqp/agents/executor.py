"""The executor: interprets one step against the live browser (PRD §6).

It never judges pass/fail (that's the evaluator or the assertion engine) and
never carries asserted values (that's the engine, in code). It acts, records the
trace, and reports the resulting snapshot.
"""

from __future__ import annotations

from collections.abc import Sequence

from aqp.agents.prompts import (
    EXECUTOR_SYSTEM,
    EXTRACTOR_SYSTEM,
    SUBMIT_TABLE_TOOL,
    executor_prompt,
    extractor_prompt,
)
from aqp.models import Step, ToolCall
from aqp.ports import (
    LLM,
    ActResult,
    Browser,
    ExtractResult,
    ToolInvocation,
    ToolOutput,
)

_TRACE_RESULT_LIMIT = 2000  # keep the trace readable; the full page is the snapshot


class Executor:
    """Implements :class:`aqp.ports.StepExecutor`."""

    def __init__(self, llm: LLM, browser: Browser, *, max_iterations: int) -> None:
        self._llm = llm
        self._browser = browser
        self._max_iterations = max_iterations

    def act(self, step: Step, snapshot: str) -> ActResult:
        trace: list[ToolCall] = []

        def dispatch(inv: ToolInvocation) -> ToolOutput:
            output = self._browser.call_tool(inv.name, inv.input)
            trace.append(
                ToolCall(
                    tool=inv.name,
                    arguments=inv.input,
                    result=output.content[:_TRACE_RESULT_LIMIT],
                    is_error=output.is_error,
                )
            )
            return output

        result = self._llm.converse(
            system=EXECUTOR_SYSTEM,
            prompt=executor_prompt(step, snapshot),
            tools=self._browser.tool_specs(),
            dispatch=dispatch,
            max_iterations=self._max_iterations,
        )
        return ActResult(
            summary=result.text,
            trace=trace,
            tokens=result.tokens,
            final_snapshot=self._browser.snapshot(),
        )

    def extract_table(self, step: Step, snapshot: str, columns: Sequence[str]) -> ExtractResult:
        result = self._llm.structured(
            system=EXTRACTOR_SYSTEM,
            prompt=extractor_prompt(step, snapshot, list(columns)),
            tool=SUBMIT_TABLE_TOOL,
        )
        raw_rows = result.data.get("rows", [])
        rows: list[list[str]] = []
        if isinstance(raw_rows, list):
            for raw_row in raw_rows:
                if isinstance(raw_row, list):
                    rows.append([str(cell) for cell in raw_row])
        return ExtractResult(rows=rows, tokens=result.tokens)
