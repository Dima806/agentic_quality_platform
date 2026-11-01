"""System prompts and the structured-output tool schemas for the agents.

Prompts are deliberately narrow: the executor sees one step and one snapshot, the
evaluator sees one result. Narrow per-step context is a harness decision that
buys reliability and cheap, cacheable tokens (PRD §11).
"""

from __future__ import annotations

from aqp.models import Step
from aqp.ports import ToolSpec

EXECUTOR_SYSTEM = (
    "You drive a web browser to carry out ONE Gherkin step. "
    "Work from the accessibility snapshot you are given: find elements by their "
    "snapshot reference (e.g. e12), never by a CSS or XPath selector. "
    "Call the browser tools to fulfil the step's intent, then stop. "
    "Do not invent data and do not assert values yourself."
)

EVALUATOR_SYSTEM = (
    "You judge whether ONE browser step achieved its intent, given the step text, "
    "what the executor did, and the resulting snapshot. "
    "Separate genuine app defects from recoverable execution issues: a transient "
    "load or a momentary miss is 'execution' and retryable; a wrong page or an "
    "unmet expectation is a 'defect' and is NOT retryable; a broken environment "
    "is 'infrastructure'. Report your verdict with the submit_verdict tool."
)

EXTRACTOR_SYSTEM = (
    "You read values off the current page. Locate the data the step refers to and "
    "return it verbatim as a table via submit_table. Copy values EXACTLY as shown "
    "-- never round, reformat, or fill in blanks. You only locate values; the "
    "comparison is done elsewhere."
)

SUBMIT_VERDICT_TOOL = ToolSpec(
    name="submit_verdict",
    description="Report the judgement for the current step.",
    input_schema={
        "type": "object",
        "properties": {
            "passed": {"type": "boolean"},
            "failure_class": {
                "type": "string",
                "enum": ["defect", "execution", "infrastructure"],
                "description": "Only when passed is false.",
            },
            "retryable": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["passed", "reason"],
    },
)

SUBMIT_TABLE_TOOL = ToolSpec(
    name="submit_table",
    description="Return the on-screen table exactly as displayed (header row first).",
    input_schema={
        "type": "object",
        "properties": {
            "rows": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
            }
        },
        "required": ["rows"],
    },
)


def executor_prompt(step: Step, snapshot: str) -> str:
    extra = ""
    if step.datatable is not None:
        extra = f"\n\nData table:\n{step.datatable.rows}"
    elif step.docstring is not None:
        extra = f"\n\nText block:\n{step.docstring}"
    return f"Step: {step.keyword} {step.text}{extra}\n\nCurrent snapshot:\n{snapshot}"


def evaluator_prompt(step: Step, action_summary: str, snapshot: str) -> str:
    return (
        f"Step: {step.keyword} {step.text}\n\n"
        f"What the executor did:\n{action_summary}\n\n"
        f"Resulting snapshot:\n{snapshot}"
    )


def extractor_prompt(step: Step, snapshot: str, columns: list[str]) -> str:
    return (
        f"Step: {step.keyword} {step.text}\n\n"
        f"Return a table with these columns, in this order: {columns}\n\n"
        f"Current snapshot:\n{snapshot}"
    )
