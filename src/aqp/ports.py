"""Ports: the narrow typed interfaces between the deterministic core and the
outside world (the browser, the model).

The core depends only on these Protocols, so the per-step loop, the executor
logic, and the evaluator are unit-testable with fakes — no live browser or model
(PRD §14 step 12). Real adapters live in :mod:`aqp.browser` and :mod:`aqp.agents`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from aqp.models import Step, TokenUsage, ToolCall, Verdict


@dataclass(frozen=True)
class ToolSpec:
    """A browser tool offered to the model (name + JSON-schema inputs)."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolInvocation:
    """A tool call the model asked for."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolOutput:
    """The result of running a tool, fed back to the model."""

    content: str
    is_error: bool = False


@dataclass(frozen=True)
class LLMResult:
    text: str
    tokens: TokenUsage
    stop_reason: str


@dataclass(frozen=True)
class StructuredResult:
    """A forced single tool call whose JSON input is the structured answer."""

    data: dict[str, Any]
    tokens: TokenUsage


@dataclass
class ActResult:
    """What the executor did for one step: a summary, the trace, tokens, and the
    snapshot after acting."""

    summary: str = ""
    trace: list[ToolCall] = field(default_factory=list)
    tokens: TokenUsage = field(default_factory=TokenUsage)
    final_snapshot: str = ""


@dataclass
class ExtractResult:
    """On-screen values the model located for a data-assertion step (PRD §7)."""

    rows: list[list[str]] = field(default_factory=list)
    tokens: TokenUsage = field(default_factory=TokenUsage)


@dataclass
class Judgement:
    """The evaluator's verdict plus the tokens it cost."""

    verdict: Verdict
    tokens: TokenUsage = field(default_factory=TokenUsage)


# --------------------------------------------------------------------------- #
# Protocols
# --------------------------------------------------------------------------- #


class LLM(Protocol):
    """A reasoning model behind the Messages API (or a fake)."""

    def converse(
        self,
        *,
        system: str,
        prompt: str,
        tools: Sequence[ToolSpec],
        dispatch: Callable[[ToolInvocation], ToolOutput],
        max_iterations: int,
    ) -> LLMResult:
        """Run a tool-use loop, calling ``dispatch`` for each tool request."""
        ...

    def structured(self, *, system: str, prompt: str, tool: ToolSpec) -> StructuredResult:
        """Force a single call to ``tool`` and return its JSON input."""
        ...


class Browser(Protocol):
    """The one layer allowed to talk to the browser. Addresses elements by
    snapshot reference, never a selector (PRD §5)."""

    def snapshot(self) -> str: ...

    def tool_specs(self) -> list[ToolSpec]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput: ...

    def screenshot(self, dest: Path) -> bool: ...

    def close(self) -> None: ...


class StepExecutor(Protocol):
    """Interprets a single step against the live browser (PRD §6)."""

    def act(self, step: Step, snapshot: str) -> ActResult: ...

    def extract_table(self, step: Step, snapshot: str, columns: Sequence[str]) -> ExtractResult:
        """Locate the on-screen table matching ``columns`` and return its rows.

        The model only *locates* values; comparison happens in code (PRD §7).
        """
        ...


class StepEvaluator(Protocol):
    """Judges a step's result: pass, or fail with a retry/stop decision (PRD §6)."""

    def judge(self, step: Step, act: ActResult) -> Judgement: ...
