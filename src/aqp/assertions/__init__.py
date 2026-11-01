"""Deterministic assertion handling. The data never passes through the model's
mouth (PRD §7)."""

from __future__ import annotations

from aqp.assertions.engine import (
    compare_table,
    compare_text,
    expected_table,
    match_cell,
    step_carries_data,
)

__all__ = [
    "compare_table",
    "compare_text",
    "expected_table",
    "match_cell",
    "step_carries_data",
]
