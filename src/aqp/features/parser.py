"""Convert a pytest-bdd parse tree into our typed :class:`Feature` model.

``And``/``But`` steps inherit the semantic type of the step above them, which is
exactly the ``given``/``when``/``then`` distinction the loop needs to decide who
judges a step (PRD §4).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pytest_bdd import exceptions as bdd_exceptions
from pytest_bdd.parser import FeatureParser
from pytest_bdd.parser import Step as BddStep

from aqp.errors import FeatureValidationError
from aqp.models import DataTable, Feature, Scenario, Step, StepType

# Gherkin parse errors raised by pytest-bdd that mean "this isn't valid".
_PARSE_ERRORS: tuple[type[Exception], ...] = (
    bdd_exceptions.FeatureError,
    bdd_exceptions.TokenError,
    bdd_exceptions.GherkinParseError,
    bdd_exceptions.BackgroundError,
    bdd_exceptions.RuleError,
    bdd_exceptions.ScenarioError,
    bdd_exceptions.StepError,
)


def parse_feature_file(path: Path) -> Feature:
    """Parse and validate one ``.feature`` file into a :class:`Feature`.

    Raises :class:`FeatureValidationError` on malformed Gherkin, with the file
    named so failures are diagnosable (PRD goal 2).
    """
    path = path.resolve()
    try:
        parsed = FeatureParser(basedir=str(path.parent), filename=path.name).parse()
    except _PARSE_ERRORS as exc:
        raise FeatureValidationError(f"{path}: {exc}") from exc
    except FileNotFoundError as exc:
        raise FeatureValidationError(f"{path}: file not found") from exc

    scenarios = [
        Scenario(name=template.name, steps=_convert_steps(template.steps))
        for template in parsed.scenarios.values()
    ]
    return Feature(name=parsed.name, path=str(path), scenarios=scenarios)


def _convert_steps(raw_steps: Sequence[BddStep]) -> list[Step]:
    steps: list[Step] = []
    for i, raw in enumerate(raw_steps, start=1):
        table = raw.datatable
        datatable = (
            DataTable(rows=[[str(cell) for cell in row] for row in table.raw()])
            if table is not None
            else None
        )
        steps.append(
            Step(
                index=i,
                keyword=raw.keyword.strip(),
                type=StepType(raw.type),
                text=raw.name,
                line_number=raw.line_number,
                datatable=datatable,
                docstring=raw.docstring,
            )
        )
    return steps
