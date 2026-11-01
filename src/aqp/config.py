"""Runtime configuration.

Nothing operational is hard-coded: model IDs, the attempt limit, the MCP
endpoint, and concurrency are all configuration (PRD §5). Precedence, lowest to
highest: built-in defaults -> ``[tool.aqp]`` in ``aqp.toml`` or ``pyproject.toml``
-> ``AQP_*`` environment variables. The API key comes only from the environment.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from aqp.errors import ConfigurationError

_API_KEY_ENV = "ANTHROPIC_API_KEY"
_ENV_PREFIX = "AQP_"


@dataclass(frozen=True, slots=True)
class Config:
    executor_model: str = "claude-sonnet-5-5"  # capable model drives the browser
    evaluator_model: str = "claude-haiku-5-5"  # cheaper model judges each step
    max_attempts: int = 2  # per step, then stop
    mcp_endpoint: str = "stdio://@playwright/mcp"
    max_parallel: int = 2  # fits a 2-CPU Codespace
    max_tool_iterations: int = 8  # executor tool-use turns per step
    executor_max_tokens: int = 2048
    evaluator_max_tokens: int = 1024
    artifacts_dir: str = "artifacts"
    anthropic_api_key: str | None = None

    @classmethod
    def load(cls, start: Path | None = None) -> Config:
        """Build a config from defaults, a TOML table, and the environment."""
        cfg = cls()
        table = _read_toml_table(start or Path.cwd())
        if table:
            cfg = replace(cfg, **_coerce(cfg, table))
        env_overrides = {
            f.name: os.environ[_ENV_PREFIX + f.name.upper()]
            for f in fields(cls)
            if f.name != "anthropic_api_key" and (_ENV_PREFIX + f.name.upper()) in os.environ
        }
        if env_overrides:
            cfg = replace(cfg, **_coerce(cfg, env_overrides))
        return replace(cfg, anthropic_api_key=os.environ.get(_API_KEY_ENV, cfg.anthropic_api_key))

    def require_api_key(self) -> str:
        if not self.anthropic_api_key:
            raise ConfigurationError(
                f"{_API_KEY_ENV} is not set. Export it before running against a live model."
            )
        return self.anthropic_api_key


def _read_toml_table(start: Path) -> dict[str, Any]:
    """Return the ``[tool.aqp]`` / top-level ``aqp.toml`` table, searching upward."""
    for directory in (start, *start.parents):
        aqp_toml = directory / "aqp.toml"
        if aqp_toml.is_file():
            return _load_toml(aqp_toml)
        pyproject = directory / "pyproject.toml"
        if pyproject.is_file():
            tool = _load_toml(pyproject).get("tool", {})
            if isinstance(tool, dict) and isinstance(tool.get("aqp"), dict):
                return dict(tool["aqp"])
            return {}
    return {}


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def _coerce(cfg: Config, values: dict[str, Any]) -> dict[str, Any]:
    """Keep only known keys and coerce them to each field's declared type."""
    types = {f.name: f.type for f in fields(cfg)}
    coerced: dict[str, Any] = {}
    for key, raw in values.items():
        if key not in types or key == "anthropic_api_key":  # the key comes only from the env
            continue
        coerced[key] = int(raw) if types[key] == "int" else str(raw)
    return coerced
