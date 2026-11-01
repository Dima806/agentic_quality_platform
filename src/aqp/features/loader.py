"""Collect and validate ``.feature`` files. Fail early with clear errors."""

from __future__ import annotations

from pathlib import Path

from aqp.errors import FeatureValidationError
from aqp.features.parser import parse_feature_file
from aqp.models import Feature


def collect_feature_files(path: Path) -> list[Path]:
    """Return the ``.feature`` files at ``path`` (a file, or a dir searched recursively)."""
    if path.is_file():
        if path.suffix != ".feature":
            raise FeatureValidationError(f"{path}: not a .feature file")
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.feature"))
    raise FeatureValidationError(f"{path}: no such file or directory")


def load_feature(path: Path) -> Feature:
    """Validate and parse a single feature file."""
    return parse_feature_file(path)


def load_features(path: Path) -> list[Feature]:
    """Collect, validate, and parse every feature under ``path``.

    Raises if nothing is found, so an empty or mistyped path fails loudly rather
    than reporting a vacuous success.
    """
    files = collect_feature_files(path)
    if not files:
        raise FeatureValidationError(f"{path}: no .feature files found")
    return [parse_feature_file(file) for file in files]
