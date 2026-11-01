"""The one hard boundary, enforced in a test (PRD §5).

Only ``aqp.browser`` may talk to the browser MCP server, no module imports a raw
browser driver, and the features package stays pure. The ruff ``playwright`` ban
and the import-linter contracts guard the same lines; this is defense-in-depth.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "aqp"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _py_files() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _is_in(module: str, roots: tuple[str, ...]) -> bool:
    return any(module == r or module.startswith(r + ".") for r in roots)


def test_only_browser_talks_to_mcp() -> None:
    offenders = [
        str(f.relative_to(SRC))
        for f in _py_files()
        if f.relative_to(SRC).parts[0] != "browser" and _is_in_any(_imports(f), ("mcp",))
    ]
    assert offenders == [], f"mcp imported outside aqp.browser: {offenders}"


def test_no_raw_browser_driver_anywhere() -> None:
    offenders = [
        str(f.relative_to(SRC)) for f in _py_files() if _is_in_any(_imports(f), ("playwright",))
    ]
    assert offenders == [], f"a raw browser driver is imported (use the MCP client): {offenders}"


def test_features_package_is_pure() -> None:
    downstream = ("aqp.browser", "aqp.agents", "aqp.runner", "aqp.assertions")
    for f in (SRC / "features").rglob("*.py"):
        bad = [m for m in _imports(f) if _is_in(m, downstream)]
        assert bad == [], f"{f.name} imports downstream layers: {bad}"


def _is_in_any(modules: set[str], roots: tuple[str, ...]) -> bool:
    return any(_is_in(m, roots) for m in modules)
