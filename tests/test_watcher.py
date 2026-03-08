"""Tests for the file watcher."""

import time
from pathlib import Path

from docs_plus_plus.server.watcher import _get_mtimes, WATCH_PATTERNS


class TestGetMtimes:
    def test_returns_empty_for_no_artifacts(self, tmp_path):
        mtimes = _get_mtimes(tmp_path)
        assert mtimes == {}

    def test_detects_existing_artifacts(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        (target / "manifest.json").write_text("{}")
        (target / "catalog.json").write_text("{}")

        mtimes = _get_mtimes(tmp_path)
        assert len(mtimes) == 2
        assert all(isinstance(v, float) for v in mtimes.values())

    def test_detects_modification(self, tmp_path):
        target = tmp_path / "target"
        target.mkdir()
        manifest = target / "manifest.json"
        manifest.write_text("{}")

        mtimes_before = _get_mtimes(tmp_path)
        time.sleep(0.05)
        manifest.write_text('{"updated": true}')

        mtimes_after = _get_mtimes(tmp_path)
        assert mtimes_after != mtimes_before
