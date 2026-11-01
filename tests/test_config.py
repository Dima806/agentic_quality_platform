"""Configuration precedence: defaults -> TOML -> env; API key from env only."""

from __future__ import annotations

from pathlib import Path

import pytest

from aqp.config import Config
from aqp.errors import ConfigurationError


def test_defaults() -> None:
    cfg = Config()
    assert cfg.max_attempts == 2
    assert cfg.max_parallel == 2
    assert cfg.executor_model == "claude-sonnet-5-5"
    assert cfg.evaluator_model == "claude-haiku-5-5"


def test_toml_overrides_defaults(tmp_path: Path) -> None:
    (tmp_path / "aqp.toml").write_text("max_attempts = 7\nexecutor_model = 'x'\n", encoding="utf-8")
    cfg = Config.load(start=tmp_path)
    assert cfg.max_attempts == 7
    assert cfg.executor_model == "x"


def test_env_beats_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "aqp.toml").write_text("max_attempts = 7\n", encoding="utf-8")
    monkeypatch.setenv("AQP_MAX_ATTEMPTS", "9")
    cfg = Config.load(start=tmp_path)
    assert cfg.max_attempts == 9


def test_api_key_from_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cfg = Config.load(start=tmp_path)
    assert cfg.require_api_key() == "sk-test"


def test_require_api_key_raises_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = Config.load(start=tmp_path)
    with pytest.raises(ConfigurationError):
        cfg.require_api_key()
