"""Command-line entry point: ``aqp run <path-to-feature-or-dir>`` (PRD §14).

``--collect-only`` validates and parses features without a browser or model --
useful in CI and as a quick syntax check.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from aqp.config import Config
from aqp.errors import AQPError
from aqp.features import load_features
from aqp.models import (
    Feature,
    FeatureOutcome,
    ScenarioReport,
    ScenarioResult,
    SuiteSummary,
)

_console = Console()


@click.group()
@click.version_option(package_name="agentic-quality-platform")
def cli() -> None:
    """Run plain-language Gherkin feature files as live browser tests."""


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_dir", type=click.Path(path_type=Path), default=None,
              help="Artifacts directory (defaults to the configured artifacts_dir).")
@click.option("--collect-only", is_flag=True,
              help="Validate and parse features, then print them. No browser or model.")
def run(path: Path, out_dir: Path | None, collect_only: bool) -> None:
    """Run the feature(s) at PATH."""
    config = Config.load()
    try:
        features = load_features(path)
    except AQPError as exc:
        raise click.ClickException(str(exc)) from exc

    if collect_only:
        _print_collection(features)
        return

    root = out_dir or Path(config.artifacts_dir)
    try:
        summary = _execute(features, config=config, root=root)
    except AQPError as exc:
        raise click.ClickException(str(exc)) from exc
    _print_summary(summary)
    if summary.features_failed or summary.features_blocked or summary.missing_reports:
        raise SystemExit(1)


def _execute(features: list[Feature], *, config: Config, root: Path) -> SuiteSummary:
    # Imported lazily so --collect-only needs neither a browser nor an API key.
    from aqp.agents import AnthropicLLM, Evaluator, Executor
    from aqp.browser import MCPBrowserClient
    from aqp.runner import ArtifactWriter, run_scenario, summarize

    key = config.require_api_key()
    browser = MCPBrowserClient(config)
    executor = Executor(
        AnthropicLLM(
            api_key=key, model=config.executor_model, max_tokens=config.executor_max_tokens
        ),
        browser,
        max_iterations=config.max_tool_iterations,
    )
    evaluator = Evaluator(
        AnthropicLLM(
            api_key=key, model=config.evaluator_model, max_tokens=config.evaluator_max_tokens
        )
    )

    outcomes: list[FeatureOutcome] = []
    browser.start()
    try:
        for feature in features:
            reports: list[ScenarioReport] = []
            for scenario in feature.scenarios:
                writer = ArtifactWriter(root, feature.name, scenario.name)
                report = run_scenario(
                    scenario,
                    feature_name=feature.name,
                    browser=browser,
                    executor=executor,
                    evaluator=evaluator,
                    config=config,
                    on_step=writer.record_step,
                    screenshot_dir=writer.screenshots,
                )
                writer.finalize(report)
                reports.append(report)
            outcomes.append(
                FeatureOutcome(
                    feature=feature.name,
                    path=feature.path,
                    result=_feature_result(reports),
                    scenarios=reports,
                )
            )
    finally:
        browser.close()

    return summarize(outcomes, max_parallel=config.max_parallel)


def _feature_result(reports: Sequence[ScenarioReport]) -> ScenarioResult:
    results = {r.result for r in reports}
    if ScenarioResult.FAILED in results:
        return ScenarioResult.FAILED
    if ScenarioResult.BLOCKED in results:
        return ScenarioResult.BLOCKED
    return ScenarioResult.PASSED


def _print_collection(features: list[Feature]) -> None:
    for feature in features:
        _console.print(f"[bold]{feature.name}[/bold]  [dim]{feature.path}[/dim]")
        for scenario in feature.scenarios:
            _console.print(f"  Scenario: {scenario.name}")
            for step in scenario.steps:
                data = " [dim](+data)[/dim]" if step.datatable or step.docstring else ""
                _console.print(f"    {step.index}. {step.keyword} {step.text}{data}")


def _print_summary(summary: SuiteSummary) -> None:
    table = Table(title="Suite summary", show_header=False)
    table.add_row("features", f"{summary.features_passed}/{summary.features_total} passed")
    table.add_row("blocked", str(summary.features_blocked))
    table.add_row("steps", f"{summary.steps_passed}/{summary.steps_total}")
    table.add_row(
        "tokens",
        f"{summary.tokens.total} total · {summary.tokens.cached_pct}% cached",
    )
    table.add_row("duration", f"{summary.duration_s}s  (max_parallel={summary.max_parallel})")
    if summary.missing_reports:
        table.add_row("missing", ", ".join(summary.missing_reports))
    _console.print(table)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
