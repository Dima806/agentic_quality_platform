"""Stream evidence to disk, memory-aware (PRD §1, §8).

Per-step results are appended to ``steps.jsonl`` as they complete, so a long run
never holds the whole thing in memory; ``report.json`` is written at the end.
"""

from __future__ import annotations

import json
from pathlib import Path

from aqp.models import ScenarioReport, StepReport


class ArtifactWriter:
    """Writes one scenario's artifacts under ``<root>/<feature>/<scenario>/``."""

    def __init__(self, root: Path, feature: str, scenario: str) -> None:
        self.dir = root / _slug(feature) / _slug(scenario)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.screenshots = self.dir / "screenshots"
        self._steps_path = self.dir / "steps.jsonl"
        # Start fresh so a re-run doesn't append to stale evidence.
        self._steps_path.write_text("", encoding="utf-8")

    def record_step(self, step: StepReport) -> None:
        """Append one step's status/trace/tokens as it finishes."""
        line = json.dumps(step.model_dump(mode="json"), ensure_ascii=False)
        with self._steps_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def finalize(self, report: ScenarioReport) -> Path:
        """Write the machine-readable ``report.json`` and return its path."""
        path = self.dir / "report.json"
        path.write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path


def _slug(name: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in name.strip().lower())
    return "-".join(filter(None, cleaned.split("-"))) or "unnamed"
