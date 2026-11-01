"""Artifact streaming: steps.jsonl appended per step, report.json at the end."""

from __future__ import annotations

import json
from pathlib import Path

from aqp.models import ScenarioReport, ScenarioResult, StepReport, StepStatus
from aqp.runner import ArtifactWriter


def test_streams_steps_then_writes_report(tmp_path: Path) -> None:
    writer = ArtifactWriter(tmp_path, "Refund flow", "Customer requests a refund")

    writer.record_step(StepReport(n=1, text="given", keyword="Given", status=StepStatus.PASSED))
    writer.record_step(StepReport(n=2, text="then", keyword="Then", status=StepStatus.FAILED))

    lines = (writer.dir / "steps.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["status"] == "PASSED"

    report = ScenarioReport(
        feature="Refund flow",
        scenario="Customer requests a refund",
        result=ScenarioResult.FAILED,
        steps_total=2,
        steps_passed=1,
    )
    path = writer.finalize(report)
    assert path.name == "report.json"
    assert json.loads(path.read_text(encoding="utf-8"))["result"] == "FAILED"
    # directory names are slugged from the feature/scenario
    assert writer.dir == tmp_path / "refund-flow" / "customer-requests-a-refund"
