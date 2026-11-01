"""Feature discovery and validation."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from aqp.errors import FeatureValidationError
from aqp.features import collect_feature_files, load_features

MINIMAL = textwrap.dedent("""\
    Feature: F
      Scenario: S
        Given something
""")


def _feature(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(MINIMAL, encoding="utf-8")
    return path


def test_collect_single_file(tmp_path: Path) -> None:
    f = _feature(tmp_path / "a.feature")
    assert collect_feature_files(f) == [f]


def test_collect_directory_is_recursive_and_sorted(tmp_path: Path) -> None:
    _feature(tmp_path / "b.feature")
    _feature(tmp_path / "nested" / "a.feature")
    found = collect_feature_files(tmp_path)
    assert found == sorted(found)  # deterministic order
    assert {p.name for p in found} == {"a.feature", "b.feature"}  # recursive


def test_non_feature_file_rejected(tmp_path: Path) -> None:
    other = tmp_path / "notes.txt"
    other.write_text("hi", encoding="utf-8")
    with pytest.raises(FeatureValidationError):
        collect_feature_files(other)


def test_missing_path_rejected(tmp_path: Path) -> None:
    with pytest.raises(FeatureValidationError):
        collect_feature_files(tmp_path / "nope")


def test_load_features_on_empty_dir_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(FeatureValidationError):
        load_features(tmp_path)


def test_load_features_parses_all(tmp_path: Path) -> None:
    _feature(tmp_path / "a.feature")
    _feature(tmp_path / "c.feature")
    features = load_features(tmp_path)
    assert [f.name for f in features] == ["F", "F"]
