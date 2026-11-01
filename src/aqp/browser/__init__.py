"""The browser boundary. **Only this package may talk to the browser-automation
MCP server, and no selector ever appears above it** (PRD §5). Enforced by the
ruff ``playwright`` ban, the import-linter contract, and ``tests/test_architecture.py``.
"""

from __future__ import annotations

from aqp.browser.mcp_client import MCPBrowserClient

__all__ = ["MCPBrowserClient"]
