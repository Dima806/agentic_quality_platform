"""The Claude Platform API adapter implementing :class:`aqp.ports.LLM`.

This is the only place the Anthropic SDK is imported. The executor and evaluator
depend on the port, so they stay testable with a fake (PRD §5, §14).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, cast

from anthropic import Anthropic
from anthropic.types import (
    Message,
    MessageParam,
    TextBlock,
    ToolParam,
    ToolUseBlock,
    Usage,
)

from aqp.models import TokenUsage
from aqp.ports import LLM, LLMResult, StructuredResult, ToolInvocation, ToolOutput, ToolSpec


class AnthropicLLM(LLM):
    """One instance per role (executor / evaluator) — model and budget are fixed."""

    def __init__(self, *, api_key: str, model: str, max_tokens: int) -> None:
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def converse(
        self,
        *,
        system: str,
        prompt: str,
        tools: Sequence[ToolSpec],
        dispatch: Callable[[ToolInvocation], ToolOutput],
        max_iterations: int,
    ) -> LLMResult:
        tool_params = _tool_params(tools)
        conversation: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        tokens = TokenUsage()
        final_text = ""
        stop_reason = "end_turn"

        for _ in range(max_iterations):
            message = self._create(system=system, conversation=conversation, tools=tool_params)
            tokens = tokens + _usage(message.usage)
            stop_reason = message.stop_reason or "end_turn"
            final_text = _text_of(message)

            tool_uses = [b for b in message.content if isinstance(b, ToolUseBlock)]
            if not tool_uses:
                break

            conversation.append({"role": "assistant", "content": _echo_content(message)})
            results: list[dict[str, Any]] = []
            for tu in tool_uses:
                output = dispatch(ToolInvocation(id=tu.id, name=tu.name, input=_as_dict(tu.input)))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": output.content,
                        "is_error": output.is_error,
                    }
                )
            conversation.append({"role": "user", "content": results})

        return LLMResult(text=final_text, tokens=tokens, stop_reason=stop_reason)

    def structured(self, *, system: str, prompt: str, tool: ToolSpec) -> StructuredResult:
        message = self._create(
            system=system,
            conversation=[{"role": "user", "content": prompt}],
            tools=_tool_params([tool]),
            forced_tool=tool.name,
        )
        for block in message.content:
            if isinstance(block, ToolUseBlock) and block.name == tool.name:
                return StructuredResult(data=_as_dict(block.input), tokens=_usage(message.usage))
        return StructuredResult(data={}, tokens=_usage(message.usage))

    def _create(
        self,
        *,
        system: str,
        conversation: list[dict[str, Any]],
        tools: list[ToolParam],
        forced_tool: str | None = None,
    ) -> Message:
        tool_choice: Any = (
            {"type": "tool", "name": forced_tool} if forced_tool else {"type": "auto"}
        )
        return self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=cast("list[MessageParam]", conversation),
            tools=tools,
            tool_choice=tool_choice,
        )


def _tool_params(tools: Sequence[ToolSpec]) -> list[ToolParam]:
    return [
        cast(
            "ToolParam",
            {"name": t.name, "description": t.description, "input_schema": t.input_schema},
        )
        for t in tools
    ]


def _echo_content(message: Message) -> list[dict[str, Any]]:
    """Rebuild the assistant turn as param dicts so it can be replayed."""
    blocks: list[dict[str, Any]] = []
    for block in message.content:
        if isinstance(block, TextBlock) and block.text:
            blocks.append({"type": "text", "text": block.text})
        elif isinstance(block, ToolUseBlock):
            blocks.append(
                {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
            )
    return blocks


def _text_of(message: Message) -> str:
    return "\n".join(b.text for b in message.content if isinstance(b, TextBlock) and b.text)


def _as_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _usage(usage: Usage) -> TokenUsage:
    cache_read = usage.cache_read_input_tokens or 0
    cache_creation = usage.cache_creation_input_tokens or 0
    return TokenUsage(
        prompt=usage.input_tokens + cache_read + cache_creation,
        completion=usage.output_tokens,
        cached=cache_read,
    )
