"""Tests for the publish tarball bundling — specifically that the author's
``docglow.yml`` is shipped to Cloud so custom layer rules + ERD preference
render instead of OSS defaults (DOC-240 / U9 CLI transport)."""

from __future__ import annotations

import tarfile
from pathlib import Path

from docglow.cloud.publish import _create_tarball, _find_config_file


def _write(path: Path, text: str = "x") -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_find_config_file_prefers_yml(tmp_path: Path) -> None:
    _write(tmp_path / "docglow.yml")
    _write(tmp_path / "docglow.yaml")
    assert _find_config_file(tmp_path) == tmp_path / "docglow.yml"


def test_find_config_file_falls_back_to_yaml(tmp_path: Path) -> None:
    _write(tmp_path / "docglow.yaml")
    assert _find_config_file(tmp_path) == tmp_path / "docglow.yaml"


def test_find_config_file_absent_returns_none(tmp_path: Path) -> None:
    assert _find_config_file(tmp_path) is None


def test_create_tarball_places_config_at_root(tmp_path: Path) -> None:
    """The config must land at the tarball root (arcname == filename) because
    Cloud's coordinator extracts flat and reads ``docglow.yml`` from the root."""
    manifest = _write(tmp_path / "manifest.json", "{}")
    config = _write(tmp_path / "docglow.yml", "enable_erd: false\n")

    tarball = _create_tarball([manifest, config])
    try:
        with tarfile.open(tarball, "r:gz") as tar:
            names = tar.getnames()
        assert "docglow.yml" in names  # root, not nested under a dir
        assert "manifest.json" in names
    finally:
        tarball.unlink(missing_ok=True)
