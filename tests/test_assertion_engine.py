"""The assertion engine: exact match, no rounding, and <name> placeholders (PRD §7)."""

from __future__ import annotations

import pytest

from aqp.assertions import compare_table, compare_text, match_cell, step_carries_data
from aqp.models import DataTable, Step, StepType


def _then(text: str, **kw: object) -> Step:
    return Step(index=1, keyword="Then", type=StepType.THEN, text=text, line_number=1, **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("expected", "actual", "ok"),
    [
        ("272.00", "272.00", True),
        ("272.00", "272", False),  # no rounding
        ("272.00", "272.0", False),  # no reformatting
        ("Successful", "Successful", True),
        ("Successful", "successful", False),  # exact, case-sensitive
        ("<ref>", "REF-99", True),  # placeholder matches any non-empty
        ("<ref>", "", False),  # ...but not empty
        ("  272.00  ", "272.00", True),  # surrounding whitespace ignored
    ],
)
def test_match_cell(expected: str, actual: str, ok: bool) -> None:
    assert match_cell(expected, actual) is ok


def test_compare_table_exact_pass() -> None:
    header = ["Status", "Amount"]
    expected = [header, ["Successful", "272.00"], ["Pending", "<ref>"]]
    actual = [header, ["Successful", "272.00"], ["Pending", "ABC-1"]]
    assert compare_table(expected, actual).ok


def test_compare_table_numeric_mismatch_fails() -> None:
    expected = [["Amount"], ["272.00"]]
    actual = [["Amount"], ["272"]]
    result = compare_table(expected, actual)
    assert not result.ok
    assert result.mismatches


def test_compare_table_row_count_mismatch() -> None:
    result = compare_table([["A"], ["1"]], [["A"]])
    assert not result.ok
    assert "row count" in result.mismatches[0]


def test_compare_table_column_count_mismatch() -> None:
    result = compare_table([["A", "B"]], [["A"]])
    assert not result.ok


def test_compare_text_exact_ignoring_trailing_ws() -> None:
    assert compare_text("line one\nline two  ", "line one\nline two").ok
    assert not compare_text("hello", "world").ok


@pytest.mark.parametrize(
    ("step", "carries"),
    [
        (_then("the table should show", datatable=DataTable(rows=[["A"], ["1"]])), True),
        (_then('the message says "done"'), True),
        (_then("the total should be 272.00"), True),
        (_then("the page is visible"), False),
    ],
)
def test_step_carries_data(step: Step, carries: bool) -> None:
    assert step_carries_data(step) is carries


def test_step_carries_data_docstring() -> None:
    assert step_carries_data(_then("the body says", docstring="hello"))
