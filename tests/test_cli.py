"""CLI smoke tests — `aqp run --collect-only` needs no browser or model."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from aqp.cli import cli

FEATURE = textwrap.dedent("""\
    Feature: Refund flow
      Scenario: Customer requests a refund
        Given a user is on the orders page
        When the user submits the refund with reason "Damaged"
""")


def test_collect_only_prints_steps(tmp_path: Path) -> None:
    path = tmp_path / "refund.feature"
    path.write_text(FEATURE, encoding="utf-8")

    result = CliRunner().invoke(cli, ["run", "--collect-only", str(path)])
    assert result.exit_code == 0
    assert "Refund flow" in result.output
    assert "a user is on the orders page" in result.output


def test_malformed_feature_exits_nonzero(tmp_path: Path) -> None:
    path = tmp_path / "bad.feature"
    path.write_text("Featur: typo\n", encoding="utf-8")

    result = CliRunner().invoke(cli, ["run", "--collect-only", str(path)])
    assert result.exit_code != 0
    assert "bad.feature" in result.output


def test_run_without_api_key_fails_cleanly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    path = tmp_path / "refund.feature"
    path.write_text(FEATURE, encoding="utf-8")

    result = CliRunner().invoke(cli, ["run", str(path)])
    assert result.exit_code != 0
    assert "ANTHROPIC_API_KEY" in result.output  # a clean message, not a traceback
    assert result.exception is None or isinstance(result.exception, SystemExit)
