"""Shared fakes and builders.

The deterministic core depends only on the :mod:`aqp.ports` Protocols, so these
fakes stand in for the browser, executor, and evaluator — no live browser or
model is needed to test the loop, parser, or assertion engine (PRD §14 step 12).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from aqp.errors import InfrastructureError
from aqp.models import (
    DataTable,
    Scenario,
    Step,
    StepType,
    TokenUsage,
    ToolCall,
    Verdict,
)
from aqp.ports import (
    ActResult,
    ExtractResult,
    Judgement,
    ToolOutput,
    ToolSpec,
)

ACT_TOKENS = TokenUsage(prompt=10, completion=2, cached=4)
JUDGE_TOKENS = TokenUsage(prompt=5, completion=1)


class FakeBrowser:
    """A :class:`aqp.ports.Browser` that returns canned snapshots."""

    def __init__(self, snapshot: str = "<page/>") -> None:
        self._snapshot = snapshot
        self.closed = False

    def snapshot(self) -> str:
        return self._snapshot

    def tool_specs(self) -> list[ToolSpec]:
        return [ToolSpec(name="browser_click", description="click", input_schema={})]

    def call_tool(self, name: str, arguments: dict[str, object]) -> ToolOutput:
        return ToolOutput(content=f"ran {name}")

    def screenshot(self, dest: Path) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG")
        return True

    def close(self) -> None:
        self.closed = True


class RaisingBrowser(FakeBrowser):
    """A browser whose snapshot fails as broken infrastructure."""

    def snapshot(self) -> str:
        raise InfrastructureError("browser won't start")


class FakeExecutor:
    """A :class:`aqp.ports.StepExecutor` with a fixed extracted table."""

    def __init__(self, table_rows: Sequence[Sequence[str]] | None = None) -> None:
        self.table_rows = [list(r) for r in (table_rows or [])]
        self.act_calls = 0
        self.extract_calls = 0

    def act(self, step: Step, snapshot: str) -> ActResult:
        self.act_calls += 1
        return ActResult(
            summary="did it",
            trace=[ToolCall(tool="browser_click", arguments={})],
            tokens=ACT_TOKENS,
            final_snapshot=snapshot,
        )

    def extract_table(
        self, step: Step, snapshot: str, columns: Sequence[str]
    ) -> ExtractResult:
        self.extract_calls += 1
        return ExtractResult(rows=self.table_rows, tokens=ACT_TOKENS)


class FakeEvaluator:
    """A :class:`aqp.ports.StepEvaluator` that replays scripted verdicts."""

    def __init__(self, verdicts: Sequence[Verdict] | None = None) -> None:
        self.verdicts = list(verdicts or [])
        self.calls = 0

    def judge(self, step: Step, act: ActResult) -> Judgement:
        self.calls += 1
        verdict = self.verdicts.pop(0) if self.verdicts else Verdict(passed=True)
        return Judgement(verdict=verdict, tokens=JUDGE_TOKENS)


def action_step(index: int, keyword: str, text: str, step_type: StepType) -> Step:
    return Step(index=index, keyword=keyword, type=step_type, text=text, line_number=index)


def make_scenario(texts: Sequence[str], name: str = "scenario") -> Scenario:
    """A scenario of simple When steps (action path — judged by the evaluator)."""
    steps = [action_step(i, "When", t, StepType.WHEN) for i, t in enumerate(texts, start=1)]
    return Scenario(name=name, steps=steps)


def table_then_step(rows: Sequence[Sequence[str]], index: int = 1) -> Step:
    return Step(
        index=index,
        keyword="Then",
        type=StepType.THEN,
        text="the results table should be shown with the following values",
        line_number=index,
        datatable=DataTable(rows=[list(r) for r in rows]),
    )
