"""Parser & loader: typed steps, data tables, doc-strings, and clear failures."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from aqp.errors import FeatureValidationError
from aqp.features import load_feature
from aqp.features.parser import parse_feature_file
from aqp.models import StepType

REFUND = textwrap.dedent("""\
    Feature: Refund flow

      Scenario: Customer requests a refund for a delivered order
        Given a user is on the orders page
        When the user opens their most recent delivered order
        And the user finds the refund control and clicks it
        Then the refund page should be visible
        When the user submits the refund with reason "Damaged on arrival"
        Then the confirmation page should be visible
        Then the results table should be shown with the following values
          | Status      | Order | Reference | Amount |
          | Successful  | <id>  | <ref>     | 272.00 |
""")


def _write(tmp_path: Path, text: str, name: str = "f.feature") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_parses_ordered_typed_steps(tmp_path: Path) -> None:
    feature = parse_feature_file(_write(tmp_path, REFUND))

    assert feature.name == "Refund flow"
    assert len(feature.scenarios) == 1
    steps = feature.scenarios[0].steps
    assert [s.index for s in steps] == [1, 2, 3, 4, 5, 6, 7]
    # And inherits the semantic type of the step above it, but keeps its keyword.
    assert steps[2].keyword == "And"
    assert steps[2].type is StepType.WHEN
    assert steps[3].type is StepType.THEN


def test_data_table_preserved_verbatim(tmp_path: Path) -> None:
    feature = parse_feature_file(_write(tmp_path, REFUND))
    table_step = feature.scenarios[0].steps[6]

    assert table_step.datatable is not None
    assert table_step.datatable.header == ["Status", "Order", "Reference", "Amount"]
    # 272.00 is kept exactly as written — not normalised to 272 or 272.0.
    assert table_step.datatable.body == [["Successful", "<id>", "<ref>", "272.00"]]


def test_quoted_value_kept_in_step_text(tmp_path: Path) -> None:
    feature = parse_feature_file(_write(tmp_path, REFUND))
    assert '"Damaged on arrival"' in feature.scenarios[0].steps[4].text


def test_docstring_captured(tmp_path: Path) -> None:
    text = textwrap.dedent('''\
        Feature: Messages

          Scenario: shows a confirmation
            Then the confirmation message should say
              """
              Your refund is being processed
              """
    ''')
    feature = parse_feature_file(_write(tmp_path, text))
    assert feature.scenarios[0].steps[0].docstring == "Your refund is being processed"


def test_malformed_gherkin_raises_with_filename(tmp_path: Path) -> None:
    path = _write(tmp_path, "Featur: typo\n  Scenari: nope\n", name="bad.feature")
    with pytest.raises(FeatureValidationError) as exc:
        load_feature(path)
    assert "bad.feature" in str(exc.value)
