"""The assertion engine: compare expected vs on-screen values **in code**.

Rules (PRD §4, §7):
  * Literal cells are matched **exactly** as strings -- ``272.00`` must stay
    ``272.00``, never ``272`` or ``272.0``. Comparing strings (not parsed
    numbers) is what guarantees no rounding or reformatting.
  * A ``<name>`` placeholder (e.g. ``<ref>``) matches **any non-empty** value,
    which handles dynamic data like a generated reference number.

The model's only job at an assertion step is to *locate* the on-screen values;
everything below is pure Python with no model in the loop.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from aqp.models import AssertionResult, Step

_PLACEHOLDER = re.compile(r"^<[^<>]+>$")
_QUOTED = re.compile(r'"([^"]*)"')
_STANDALONE_NUMBER = re.compile(r"(?<!\w)\d+(?:\.\d+)?(?!\w)")


def step_carries_data(step: Step) -> bool:
    """True when a ``Then`` step carries concrete data that code must check.

    That is: a data table, a double-quoted value, a standalone number, or a
    doc-string text block. Any other ``Then`` is judged by the model (PRD §4).
    """
    if step.datatable is not None and step.datatable.rows:
        return True
    if step.docstring is not None and step.docstring.strip():
        return True
    if _QUOTED.search(step.text):
        return True
    return _STANDALONE_NUMBER.search(step.text) is not None


def match_cell(expected: str, actual: str) -> bool:
    """Match one cell: ``<name>`` matches any non-empty value, else exact string."""
    expected = expected.strip()
    actual = actual.strip()
    if _PLACEHOLDER.match(expected):
        return actual != ""
    return expected == actual


def compare_table(
    expected: Sequence[Sequence[str]], actual: Sequence[Sequence[str]]
) -> AssertionResult:
    """Compare two tables cell by cell. Dimensions must match exactly."""
    mismatches: list[str] = []
    if len(expected) != len(actual):
        mismatches.append(f"row count: expected {len(expected)}, got {len(actual)}")
        return AssertionResult(ok=False, mismatches=mismatches)

    for r, (exp_row, act_row) in enumerate(zip(expected, actual, strict=False)):
        if len(exp_row) != len(act_row):
            mismatches.append(
                f"row {r}: column count expected {len(exp_row)}, got {len(act_row)}"
            )
            continue
        for c, (exp_cell, act_cell) in enumerate(zip(exp_row, act_row, strict=False)):
            if not match_cell(exp_cell, act_cell):
                mismatches.append(f"cell [{r}][{c}]: expected {exp_cell!r}, got {act_cell!r}")

    return AssertionResult(ok=not mismatches, mismatches=mismatches)


def compare_text(expected: str, actual: str) -> AssertionResult:
    """Compare a text block / value: exact after trimming trailing whitespace per line."""
    if _normalize(expected) == _normalize(actual):
        return AssertionResult(ok=True)
    return AssertionResult(ok=False, mismatches=[f"expected {expected!r}, got {actual!r}"])


def expected_table(step: Step) -> list[list[str]]:
    """The expected rows a data-table ``Then`` step asserts (header + body)."""
    if step.datatable is None:
        return []
    return [list(row) for row in step.datatable.rows]


def _normalize(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())
