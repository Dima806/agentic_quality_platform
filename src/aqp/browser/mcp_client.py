"""The browser client: a thin, synchronous wrapper over the Playwright MCP server.

Elements are addressed by accessibility-snapshot references (e.g. ``e12``) that
the server returns -- never CSS/XPath selectors. The MCP session is async and
must stay open across calls, so this facade drives it on a dedicated event-loop
thread and exposes the synchronous :class:`aqp.ports.Browser` interface the rest
of the platform uses.
"""

from __future__ import annotations

import asyncio
import base64
import shlex
import threading
from collections.abc import Coroutine
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, TypeVar

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, ImageContent, TextContent

from aqp.config import Config
from aqp.errors import BrowserError, InfrastructureError
from aqp.ports import ToolOutput, ToolSpec

_T = TypeVar("_T")

SNAPSHOT_TOOL = "browser_snapshot"
SCREENSHOT_TOOL = "browser_take_screenshot"


class MCPBrowserClient:
    """Synchronous :class:`aqp.ports.Browser` backed by a Playwright-style MCP server."""

    def __init__(self, config: Config) -> None:
        self._params = _stdio_params(config.mcp_endpoint)
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[ToolSpec] | None = None

    # -- lifecycle --------------------------------------------------------- #

    def start(self) -> None:
        try:
            self._run(self._connect())
        except Exception as exc:  # noqa: BLE001 - any startup failure is infra
            raise InfrastructureError(f"could not start the browser MCP server: {exc}") from exc

    def close(self) -> None:
        if self._session is not None:
            self._run(self._stack.aclose())
            self._session = None
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if not self._loop.is_closed():
            self._loop.close()

    # -- Browser port ------------------------------------------------------ #

    def tool_specs(self) -> list[ToolSpec]:
        if self._tools is None:
            result = self._run(self._session_or_raise().list_tools())
            self._tools = [
                ToolSpec(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=dict(tool.input_schema),
                )
                for tool in result.tools
            ]
        return self._tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolOutput:
        result = self._run(self._session_or_raise().call_tool(name, arguments))
        if not isinstance(result, CallToolResult):
            raise BrowserError(f"tool {name!r} returned an unexpected result type")
        text = "\n".join(
            block.text for block in result.content if isinstance(block, TextContent)
        )
        return ToolOutput(content=text, is_error=bool(result.is_error))

    def snapshot(self) -> str:
        return self.call_tool(SNAPSHOT_TOOL, {}).content

    def screenshot(self, dest: Path) -> bool:
        result = self._run(self._session_or_raise().call_tool(SCREENSHOT_TOOL, {}))
        if not isinstance(result, CallToolResult):
            return False
        for block in result.content:
            if isinstance(block, ImageContent):
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(base64.b64decode(block.data))
                return True
        return False

    # -- internals --------------------------------------------------------- #

    async def _connect(self) -> None:
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._session = session

    def _session_or_raise(self) -> ClientSession:
        if self._session is None:
            raise BrowserError("browser session is not started; call start() first")
        return self._session

    def _run(self, coro: Coroutine[Any, Any, _T]) -> _T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()


def _stdio_params(endpoint: str) -> StdioServerParameters:
    """Parse ``stdio://<cmd>`` into a command + args. A bare package spec runs via npx."""
    if not endpoint.startswith("stdio://"):
        raise BrowserError(f"unsupported MCP endpoint {endpoint!r} (expected stdio://...)")
    parts = shlex.split(endpoint.removeprefix("stdio://"))
    if not parts:
        raise BrowserError("empty MCP endpoint")
    if len(parts) == 1 and parts[0] not in {"npx", "node"}:
        return StdioServerParameters(command="npx", args=["-y", parts[0]])
    return StdioServerParameters(command=parts[0], args=parts[1:])
